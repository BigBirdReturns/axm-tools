#!/usr/bin/env python3
"""Bind the rendered visual floor to static and live release workflows."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROGRAM_PATH = '      - "programs/manzanita-public-convergence/**"'
MANZANITA_PATH = '      - "manzanita/**"'


def install_dependency(text: str) -> str:
    return text.replace(
        "python -m pip install --disable-pip-version-check playwright==1.57.0",
        "python -m pip install --disable-pip-version-check Pillow==11.3.0 playwright==1.57.0",
    )


def add_program_paths(text: str) -> str:
    """Add the convergence program to every Manzanita path trigger."""
    lines = text.splitlines()
    output: list[str] = []
    for index, line in enumerate(lines):
        output.append(line)
        if line != MANZANITA_PATH:
            continue
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if next_line != PROGRAM_PATH:
            output.append(PROGRAM_PATH)
    return "\n".join(output) + ("\n" if text.endswith("\n") else "")


def insert_before(text: str, marker: str, block: str, error: str) -> str:
    if marker not in text:
        raise SystemExit(error)
    return text.replace(marker, block + marker, 1)


def static_workflow() -> None:
    path = REPO / ".github/workflows/manzanita-check.yml"
    text = install_dependency(add_program_paths(path.read_text(encoding="utf-8")))

    if "Enforce rendered photographic composition and aperture distinction" not in text:
        text = insert_before(
            text,
            "      - uses: actions/upload-artifact@v4\n",
            "      - name: Enforce rendered photographic composition and aperture distinction\n"
            "        run: python programs/manzanita-public-convergence/rendered_visual_floor.py --output ${{ runner.temp }}/manzanita-rendered-visual-floor\n",
            "Could not locate the permanent artifact-retention step",
        )

    single_path = "          path: ${{ runner.temp }}/manzanita-screens"
    block_path = (
        "          path: |\n"
        "            ${{ runner.temp }}/manzanita-screens\n"
        "            ${{ runner.temp }}/manzanita-rendered-visual-floor"
    )
    if single_path in text:
        text = text.replace(single_path, block_path, 1)

    path.write_text(text, encoding="utf-8")


def live_workflow() -> None:
    path = REPO / ".github/workflows/manzanita-live-check.yml"
    text = install_dependency(path.read_text(encoding="utf-8"))

    if "Enforce rendered photographic composition against the deployed endpoint" not in text:
        visual_step = '''      - name: Enforce rendered photographic composition against the deployed endpoint
        id: visual
        if: steps.browser.outcome == 'success'
        continue-on-error: true
        env:
          MANZANITA_URL: ${{ env.MANZANITA_BASE_URL }}/?v=${{ env.MANZANITA_SOURCE_SHA }}
        run: |
          set -o pipefail
          python programs/manzanita-public-convergence/rendered_visual_floor.py \
            --target "$MANZANITA_URL" \
            --output /tmp/manzanita-live/rendered-visual-floor 2>&1 \
            | tee /tmp/manzanita-live/visual.log

'''
        text = insert_before(
            text,
            "      - name: Retain live screenshots\n",
            visual_step,
            "Could not locate the live screenshot-retention step",
        )

    text = text.replace(
        "        if: steps.browser.outcome == 'success'\n        continue-on-error: true\n        uses: actions/upload-artifact@v4",
        "        if: steps.browser.outcome == 'success' && steps.visual.outcome == 'success'\n        continue-on-error: true\n        uses: actions/upload-artifact@v4",
        1,
    )

    for single_path in (
        "          path: ${{ runner.temp }}/manzanita-live-screens",
        "          path: ${{ runner.temp }}/manzanita-v1.6.0-live-screens",
    ):
        if single_path in text:
            screen_path = single_path.removeprefix("          path: ")
            text = text.replace(
                single_path,
                "          path: |\n"
                f"            {screen_path}\n"
                "            /tmp/manzanita-live/rendered-visual-floor",
                1,
            )
            break

    browser_env = "          BROWSER_OUTCOME: ${{ steps.browser.outcome }}"
    visual_env = "          RENDERED_VISUAL_OUTCOME: ${{ steps.visual.outcome }}"
    if browser_env in text and visual_env not in text:
        text = text.replace(browser_env, browser_env + "\n" + visual_env, 1)

    browser_outcome = '              "browser_contract": os.environ["BROWSER_OUTCOME"],'
    visual_outcome = '              "rendered_visual_floor": os.environ["RENDERED_VISUAL_OUTCOME"],'
    if browser_outcome in text and visual_outcome not in text:
        text = text.replace(browser_outcome, browser_outcome + "\n" + visual_outcome, 1)

    browser_failure = '                  "browser_tail": tail("/tmp/manzanita-live/browser.log") if outcomes["browser_contract"] != "success" else "",'
    visual_failure = '                  "rendered_visual_tail": tail("/tmp/manzanita-live/visual.log") if outcomes["rendered_visual_floor"] != "success" else "",'
    if browser_failure in text and visual_failure not in text:
        text = text.replace(browser_failure, browser_failure + "\n" + visual_failure, 1)

    upload_test = '            test "${{ steps.upload.outcome }}" = "success"'
    visual_test = '            test "${{ steps.visual.outcome }}" = "success"'
    if upload_test in text and visual_test not in text:
        text = text.replace(upload_test, visual_test + "\n" + upload_test, 1)

    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    static_workflow()
    live_workflow()
    print("Permanent static and live rendered visual gates: INSTALLED")
