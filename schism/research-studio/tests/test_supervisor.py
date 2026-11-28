"""Regression checks for the observed SCHISM 0.1.1 lifecycle boundaries."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "studio_supervisor", Path(__file__).resolve().parents[1] / "supervise_service.py")
supervisor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supervisor)


def snapshot(status="running", run="run-a", generation=4, release="release-a", jobs=None, kind="service"):
    return {"version": "0.1.1", "applications": [{
        "id": "reader", "kind": kind, "status": status, "run_id": run,
        "generation": generation, "release_id": release,
        "process": {"started_at": "2026-11-28T10:00:00Z"}}],
        "jobs": jobs or []}


def operation(job_id, operation="stop", status="succeeded", ended_at="2026-11-28T10:01:00Z"):
    return {"id": job_id, "operation": operation, "app_id": "reader", "status": status,
            "ended_at": ended_at if status in supervisor.TERMINAL_JOBS else None,
            "result": {"app_id": "reader", "status": "stopped"} if status == "succeeded" else None}


class FakeStore:
    def __init__(self, app, kind="service"):
        self.selected = app
        self.kind = kind

    def app(self, app_id, required=False):
        return self.selected

    def release(self, release_id):
        return {"application": {"kind": self.kind}}


class FakeBaseEngine:
    """Only the read boundary used by the subclass; real Engine supplies locking."""
    def __init__(self, store):
        self.store = store

    def _generation(self, app_id, expected):
        app = self.store.app(app_id)
        if app["generation"] != expected:
            raise RuntimeError("generation changed")
        return app


class SupervisorLifecycleTests(unittest.TestCase):
    def test_completed_historical_stop_does_not_mask_crash(self):
        old = operation("old-stop", ended_at="2026-11-28T09:00:00Z")
        monitor = supervisor.LifecycleMonitor(snapshot(jobs=[old]), "reader")
        with self.assertRaisesRegex(RuntimeError, "without a completed operator stop"):
            monitor.observe(snapshot(status="stopped", jobs=[old]))

    def test_stop_completed_during_adoption_snapshot_is_retained(self):
        stop = operation("stop-between-snapshot-reads")
        monitor = supervisor.LifecycleMonitor(snapshot(jobs=[stop]), "reader")
        outcome, _ = monitor.observe(snapshot(status="stopped", jobs=[stop]))
        self.assertEqual(outcome, "operator-stopped")

    def test_operator_stop_waits_for_its_success_commit(self):
        monitor = supervisor.LifecycleMonitor(snapshot(), "reader")
        outcome, _ = monitor.observe(snapshot(status="stopped", jobs=[operation("stop-now", status="running")]))
        self.assertEqual(outcome, "lifecycle-transition")
        outcome, _ = monitor.observe(snapshot(status="stopped", jobs=[operation("stop-now")]))
        self.assertEqual(outcome, "operator-stopped")

    def test_failed_stop_does_not_mask_process_failure(self):
        monitor = supervisor.LifecycleMonitor(snapshot(), "reader")
        with self.assertRaisesRegex(RuntimeError, "without a completed operator stop"):
            monitor.observe(snapshot(status="stopped", jobs=[operation("stop-failed", status="failed")]))

    def test_deploy_transient_then_replacement_leaves_new_run(self):
        monitor = supervisor.LifecycleMonitor(snapshot(), "reader")
        outcome, _ = monitor.observe(snapshot(status="stopped", jobs=[operation("deploy", "deploy", "running")]))
        self.assertEqual(outcome, "lifecycle-transition")
        outcome, _ = monitor.observe(snapshot(run="run-b", release="release-b", generation=5))
        self.assertEqual(outcome, "replacement-selected")

    def test_same_generation_replacement_is_distinct(self):
        monitor = supervisor.LifecycleMonitor(snapshot(), "reader")
        outcome, _ = monitor.observe(snapshot(run="run-b"))
        self.assertEqual(outcome, "replacement-selected")

    def test_shutdown_guard_rechecks_run_inside_engine_boundary(self):
        adopted = supervisor.ownership(snapshot()["applications"][0])
        # Snapshot-to-stop race: the store now selects a new run at the same generation.
        store = FakeStore(snapshot(run="run-b")["applications"][0])
        guard = supervisor.guarded_engine_class(FakeBaseEngine)(store, adopted)
        with self.assertRaisesRegex(RuntimeError, "ownership changed"):
            guard._generation("reader", 4)
        self.assertEqual(store.selected["run_id"], "run-b")
        store.selected = snapshot()["applications"][0]
        self.assertEqual(guard._generation("reader", 4)["run_id"], "run-a")

    def test_task_refused_at_supervision_and_guarded_stop(self):
        with self.assertRaisesRegex(RuntimeError, "service application"):
            supervisor.LifecycleMonitor(snapshot(kind="task"), "reader")
        adopted = supervisor.ownership(snapshot()["applications"][0])
        store = FakeStore(snapshot()["applications"][0], kind="task")
        guard = supervisor.guarded_engine_class(FakeBaseEngine)(store, adopted)
        with self.assertRaisesRegex(RuntimeError, "refuses task"):
            guard._generation("reader", 4)

    def test_controller_version_change_fails_closed(self):
        changed = snapshot()
        changed["version"] = "0.1.2"
        with self.assertRaisesRegex(RuntimeError, "Qualified controller"):
            supervisor.LifecycleMonitor(changed, "reader")


if __name__ == "__main__":
    unittest.main()
