# Operator Start Here

## Five-minute run

1. Open `index.html` in a current browser.
2. Select **BP-QE-001 Qualified entry with decoy and N-1 loss**.
3. Click **Run reference path**.
4. Confirm the final state is `OPERATE`, N-1 is `PASS`, known holdouts are `0`, and restoration is `100%`.
5. Open the Receipt tab or click **Export receipt**.

## Failure-boundary run

1. Select **BP-HO-002 Preexisting hidden network holdout**.
2. Click **Run reference path**.
3. Confirm that the holdout becomes visible, the gate returns `HOLD`, and the baseline is no longer treated as qualified.

## Authority-boundary run

1. Select any scenario.
2. Click **Run authority-failure path**.
3. Confirm that consequence and technical-finding actions attempted from the wrong seats are rejected and preserved in the receipt.

## Saturation run

1. Select **BP-SAT-004 Portfolio saturation boundary**.
2. Click **Run reference path**.
3. Confirm that the system holds rather than attempting to process the entire queue.

## Operator caution

The interface exposes hidden scenario truth in exported receipts because it is a research exercise. A live system would separate facilitator truth, participant views, classified evidence, releasable findings, and public reporting.
