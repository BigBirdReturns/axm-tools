# Procedure reuse composition test 2.0.0

This is the mirror test for the first interoperability run.

The first run established that a retained procedure can survive harmless page drift, stop before a changed action meaning, and reject a false success after a fresh saved-state read. This test holds the page semantics constant and makes the browser continuity contract stale instead. It reuses the published v1 fixture; no new application behavior is introduced.

## Task

Save synthetic request R-1042 for DEMO-A / KIT-01 with quantity 3 and status DRAFT.

## Hronaut source boundary

This protocol was written against public Hronaut main `7efcfbf31adc632c0fb54e7cdb79ef737e26360c`.

The public implementation compares opaque continuity evidence including a runtime epoch, workspace and tab identity, origin and policy digests, `navigationGeneration`, `humanInteractionGeneration`, and an optional marker digest. Hronaut's own integration tests require fresh review after navigation, human input, policy, tab, archive/resume and runtime changes and reject writes while continuity is suspended.

Use only Hronaut's advertised `browser_continuity` operations and returned public status/reason fields. Do not expose internal evidence, resume keys, private workspace capabilities, cookies or tokens.

## Run

1. Create one fresh Hronaut scratch workspace and one tab.
2. Open `https://bigbirdreturns.github.io/axm-tools/procedure-reuse/v1/fixture.html`.
3. Start a new fixture run. Confirm the page semantics match DEMO-A / R-1042 / KIT-01, a unique Quantity field, DRAFT, and action effect `draft.local.save`. Do not save yet.
4. Create a native Hronaut continuity checkpoint.
5. Reload that same tab once. Do not change the task or fixture state.
6. Freshly observe the page again. Record whether procedure semantics still match.
7. Before any task write, ask Hronaut for continuity status. Record its public status and reason codes.
8. Demonstrate the native continuity guard using only normal Hronaut tools. The expected result is that the stale lifetime boundary blocks the write even though page semantics still match. Do not bypass the guard, inject script, use DevTools, touch localStorage directly or substitute another browser.
9. Use read-only page evidence to confirm the fixture remains quantity 1, revision 0, zero save attempts and zero external attempts.
10. Follow Hronaut's normal inspect/reconcile flow. Do not disable or weaken the guard.
11. Take a fresh semantic observation. Only when both lifetime continuity and semantic admission are current, fill quantity 3, save exactly once, then read the saved record.
12. Report the lifetime-block result separately from the final saved-state result.

## Report

Return:

- Hronaut version.
- Same scratch workspace/tab throughout: yes/no.
- Page semantics after reload: MATCH / CHANGED / UNKNOWN.
- Hronaut continuity before reconcile: status + public reason codes.
- Write while stale: BLOCKED / NOT BLOCKED / NOT TESTED.
- Fixture state while stale: quantity, revision, save attempts.
- Continuity reconciliation: completed / failed / not attempted.
- Final semantic admission after reconcile: ADMIT / UNKNOWN.
- Final saved-state verdict: PASS / FAIL / UNKNOWN.
- Any repair, alternate browser, script injection or direct storage access.

Expected clean result: semantics MATCH, native continuity BLOCKED after reload, write BLOCKED, fixture untouched, normal reconciliation succeeds, fresh semantic admission ADMIT, one verified save, PASS.

## Boundary

This is a narrow composition test. It does not prove browser security, distributed consensus, malicious-client resistance, atomic cross-system transactions, reconnect correctness for every client, or production safety. The v1 page owns the application fixture; Hronaut owns the lifetime guard; the procedure owns semantic admission; fresh saved-state read-back owns the task outcome.
