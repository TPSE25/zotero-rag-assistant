import os
import sys
from pathlib import Path

import httpx

ROOT_DIR = Path(os.getenv("ROOT_DIR", "/var/lib/webdav/data"))
CORE_API_URL = os.getenv("CORE_API_URL", "http://core:8000/internal/file-changed")
TIMEOUT_SECONDS = float(os.getenv("REINDEX_TIMEOUT", "30"))
EVENT_TYPE = os.getenv("REINDEX_EVENT_TYPE", "PUT")


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        files.append(path)
    files.sort()
    return files


def post_file(client: httpx.Client, root: Path, file_path: Path) -> None:
    rel = str(file_path.relative_to(root)).replace(os.sep, "/")
    with file_path.open("rb") as f:
        response = client.post(
            CORE_API_URL,
            data={"filename": rel, "event_type": EVENT_TYPE},
            files={"file": (rel, f)},
        )
    response.raise_for_status()


def main() -> int:
    if not ROOT_DIR.exists() or not ROOT_DIR.is_dir():
        print(f"ROOT_DIR not found or not a directory: {ROOT_DIR}", file=sys.stderr)
        return 1

    files = iter_files(ROOT_DIR)
    if not files:
        print(f"No files found under {ROOT_DIR}")
        return 0

    print(f"Starting full reindex for {len(files)} files from {ROOT_DIR}")
    print(f"Target endpoint: {CORE_API_URL}")

    success = 0
    failed = 0

    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        for idx, path in enumerate(files, start=1):
            rel = str(path.relative_to(ROOT_DIR)).replace(os.sep, "/")
            try:
                post_file(client, ROOT_DIR, path)
                success += 1
                print(f"[{idx}/{len(files)}] OK {rel}")
            except Exception as exc:
                failed += 1
                print(f"[{idx}/{len(files)}] FAIL {rel} - {exc}", file=sys.stderr)

    print(f"Finished reindex. Success: {success}, Failed: {failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
