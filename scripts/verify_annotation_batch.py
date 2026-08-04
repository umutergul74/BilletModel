from __future__ import annotations

from pathlib import Path
import argparse
import csv
import hashlib
import json
import zipfile


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify an image-only CVAT annotation package.")
    parser.add_argument("batch_dir", type=Path)
    parser.add_argument("zip_name")
    args = parser.parse_args()

    batch_dir = args.batch_dir.resolve()
    with (batch_dir / "selected_manifest.csv").open(encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    expected_names = {row["filename"] for row in rows}
    image_names = {path.name for path in (batch_dir / "images").glob("*.jpg")}
    mismatches = [
        row["filename"]
        for row in rows
        if sha256(batch_dir / "images" / row["filename"]) != row["sha256"]
    ]
    zip_path = batch_dir / args.zip_name
    with zipfile.ZipFile(zip_path) as archive:
        zip_names = set(archive.namelist())
        bad_zip_member = archive.testzip()

    result = {
        "manifest_rows": len(rows),
        "image_files": len(image_names),
        "zip_entries": len(zip_names),
        "zip_test_bad_file": bad_zip_member,
        "manifest_hash_mismatches": mismatches,
        "image_names_match_manifest": image_names == expected_names,
        "zip_names_match_manifest": zip_names == expected_names,
        "zip_sha256": sha256(zip_path),
    }
    print(json.dumps(result, indent=2))
    if (
        bad_zip_member is not None
        or mismatches
        or image_names != expected_names
        or zip_names != expected_names
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
