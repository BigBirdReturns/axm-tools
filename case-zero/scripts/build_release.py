#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import textwrap
import zipfile
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1]
RUNNER = TOOL / "runner"
DOWNLOADS = TOOL / "downloads"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def plain_lines(markdown: str) -> list[str]:
    result: list[str] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            line = line.lstrip("#").strip().upper()
        line = line.replace("×", "x").replace("→", "->").replace("—", "-").replace("–", "-")
        line = line.replace("`", "").replace("**", "")
        if not line:
            result.append("")
            continue
        result.extend(textwrap.wrap(line, width=86, break_long_words=False, break_on_hyphens=False) or [""])
    return result


def build_pdf(markdown_path: Path, output: Path) -> None:
    lines = plain_lines(markdown_path.read_text(encoding="utf-8"))
    pages = [lines[index:index + 47] for index in range(0, len(lines), 47)] or [[]]
    page_object_numbers = [4 + index * 2 for index in range(len(pages))]
    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for index, page_lines in enumerate(pages):
        page_number = page_object_numbers[index]
        content_number = page_number + 1
        page_object = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_number} 0 R >>"
        ).encode("ascii")
        stream_lines = ["BT", "/F1 10 Tf", "50 744 Td", "14 TL"]
        for line in page_lines:
            stream_lines.append(f"({pdf_escape(line)}) Tj")
            stream_lines.append("T*")
        stream_lines.append("ET")
        stream = ("\n".join(stream_lines) + "\n").encode("latin-1", errors="replace")
        content_object = b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream"
        objects.extend([page_object, content_object])

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body = bytearray(header)
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body.extend(f"{number} 0 obj\n".encode("ascii"))
        body.extend(obj)
        body.extend(b"\nendobj\n")
    xref_offset = len(body)
    body.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    body.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    body.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    output.write_bytes(bytes(body))


def build_zip(output: Path) -> None:
    files = [path for path in sorted(RUNNER.iterdir(), key=lambda item: item.name) if path.is_file() and path.name != "PACKAGE_SHA256SUMS"]
    sums = [f"{sha256(path)}  {path.name}" for path in files]
    (RUNNER / "PACKAGE_SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8", newline="\n")
    files.append(RUNNER / "PACKAGE_SHA256SUMS")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(f"redcat_case_zero_runner_v0.1/{path.name}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def main() -> None:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    build_pdf(RUNNER / "PRE_READ.md", DOWNLOADS / "CASE_ZERO_PRE_READ.pdf")
    build_zip(DOWNLOADS / "redcat_case_zero_runner_v0.1.zip")
    print("CASE_ZERO_RELEASE_BUILT")


if __name__ == "__main__":
    main()
