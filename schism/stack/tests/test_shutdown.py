"""Persistence and observer ownership remain explicit during failed shutdown."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

import psutil

from schism_stack.engine import Engine


class ShutdownBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="schism-shutdown-")
        self.addCleanup(self.temp.cleanup)
        self.engine = Engine(Path(self.temp.name) / "operator")

    def test_database_setup_failure_closes_the_handle_and_preserves_the_error(self):
        for pragma in ("PRAGMA synchronous=FULL", "PRAGMA foreign_keys=ON"):
            failure = sqlite3.OperationalError("Injected setup failure")

            class Connection(sqlite3.Connection):
                closed = False

                def execute(self, statement, *args):
                    if statement == pragma:
                        raise failure
                    return super().execute(statement, *args)

                def close(self):
                    self.closed = True
                    super().close()

            connection = sqlite3.connect(":memory:", factory=Connection)
            with self.subTest(pragma=pragma), mock.patch("schism_stack.store.sqlite3.connect", return_value=connection):
                with self.assertRaises(sqlite3.OperationalError) as caught:
                    with self.engine.store.db():
                        self.fail("Failed setup cannot enter the caller's transaction")
                self.assertIs(caught.exception, failure)
                self.assertTrue(connection.closed)
                with self.assertRaises(sqlite3.ProgrammingError):
                    connection.execute("SELECT 1")

    def test_rollback_failure_preserves_the_original_error_without_replaying_the_body(self):
        class Connection(sqlite3.Connection):
            closed = False

            def rollback(self):
                raise sqlite3.OperationalError("Injected rollback failure")

            def close(self):
                self.closed = True
                super().close()

        connection = sqlite3.connect(":memory:", factory=Connection)
        original = RuntimeError("Original operation failed after an effect")
        effects = []
        with mock.patch("schism_stack.store.sqlite3.connect", return_value=connection):
            with self.assertRaises(RuntimeError) as caught:
                with self.engine.store.db():
                    effects.append("one effect")
                    raise original
        self.assertIs(caught.exception, original)
        self.assertEqual(effects, ["one effect"])
        self.assertTrue(connection.closed)

    def test_observer_completion_precedes_force_and_hung_observers_remain_bounded(self):
        row = {"release_id": "release", "pid": 10, "process_created": 1.0,
               "runner_pid": 20, "runner_created": 2.0, "launcher_pid": 30, "launcher_created": 3.0}
        for hangs in (False, True):
            sequence = []

            def stop(pid, created, timeout):
                sequence.append(("stop", pid))
                return True

            def wait(*, timeout):
                self.assertGreater(timeout, 0)
                self.assertLessEqual(timeout, 5)
                sequence.append(("wait", 20))
                if hangs:
                    raise psutil.TimeoutExpired(timeout, pid=20)

            observer = mock.Mock()
            observer.create_time.return_value = 2.0
            observer.wait.side_effect = wait
            with self.subTest(hung=hangs), \
                 mock.patch.object(self.engine.store, "one", return_value=row), \
                 mock.patch.object(self.engine.store, "release", return_value={"application": {"stop_timeout": 1}}), \
                 mock.patch("schism_stack.engine.stop_owned", side_effect=stop), \
                 mock.patch("schism_stack.engine.process_alive", return_value=True), \
                 mock.patch("schism_stack.engine.psutil.Process", return_value=observer):
                self.engine._stop_run("recorded-run")
            expected = [("stop", 10), ("wait", 20)]
            if hangs:
                expected.append(("stop", 20))
            expected.append(("stop", 30))
            self.assertEqual(sequence, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
