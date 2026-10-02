"""Read frozen Python constants into a private scan directory; do not publish dumps."""
import argparse
import json
from pathlib import Path
import types

from PyInstaller.archive.readers import CArchiveReader


def strings(code):
    values = []
    for value in code.co_consts:
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, bytes):
            values.append(value.decode("utf-8", errors="replace"))
        elif isinstance(value, types.CodeType):
            values.extend(strings(value))
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    archive = CArchiveReader(str(args.executable.resolve()))
    pyz = archive.open_embedded_archive("PYZ.pyz")
    count = 0
    for name in pyz.toc:
        code = pyz.extract(name)
        if isinstance(code, types.CodeType):
            (args.output / f"{name}.json").write_text(json.dumps(strings(code), ensure_ascii=True, indent=2), encoding="utf-8")
            count += 1
    print(json.dumps({"modules_extracted": count, "private_scan_directory": str(args.output)}))


if __name__ == "__main__":
    main()
