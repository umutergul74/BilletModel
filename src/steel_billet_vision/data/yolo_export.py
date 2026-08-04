from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import argparse
import csv
import hashlib
import json
import shutil

import yaml

from steel_billet_vision.annotation.cvat import load_cvat_images_xml


SPLIT_DIRECTORY = {"train": "train", "validation": "val", "test": "test"}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_image(source: Path, destination: Path) -> str:
    """Copy an image without sharing storage with the immutable source dataset."""
    shutil.copy2(source, destination)
    if _file_sha256(source) != _file_sha256(destination):
        destination.unlink(missing_ok=True)
        raise OSError(f"Image copy failed integrity verification: {source}")
    return "independent_copy"


def _ensure_terminal_jpeg_eoi(path: Path) -> str:
    """Prevent downstream JPEG repair/re-encoding without changing source pixels."""
    if path.suffix.lower() not in {".jpg", ".jpeg"}:
        return "not_jpeg"
    with path.open("rb+") as stream:
        stream.seek(-2, 2)
        if stream.read(2) == b"\xff\xd9":
            return "already_terminal_eoi"
        stream.seek(0, 2)
        stream.write(b"\xff\xd9")
    return "terminal_eoi_appended"


def _format_polygon(points: tuple[tuple[float, float], ...], width: int, height: int) -> str:
    if len(points) < 3:
        raise ValueError("A segmentation polygon must have at least three points")
    normalized: list[str] = ["0"]
    for x, y in points:
        x_normalized = min(1.0, max(0.0, x / width))
        y_normalized = min(1.0, max(0.0, y / height))
        normalized.extend((f"{x_normalized:.8f}", f"{y_normalized:.8f}"))
    return " ".join(normalized)


def export_dataset(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    project_root = config_path.parent.parent
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    images_dir = (project_root / config["paths"]["images"]).resolve()
    annotation_xml = (project_root / config["paths"]["annotation_xml"]).resolve()
    split_manifest = (project_root / config["paths"]["split_manifest"]).resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty derived dataset: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    export = load_cvat_images_xml(annotation_xml)
    images = {image.name: image for image in export.images}
    with split_manifest.open(encoding="utf-8-sig") as stream:
        split_rows = list(csv.DictReader(stream))

    counts: Counter[str] = Counter()
    instances: Counter[str] = Counter()
    copy_methods: Counter[str] = Counter()
    normalization_methods: Counter[str] = Counter()
    manifest_rows: list[dict[str, Any]] = []
    for row in split_rows:
        filename = row["filename"]
        split = row["split"]
        destination_split = SPLIT_DIRECTORY[split]
        image = images.get(filename)
        source_path = images_dir / filename
        if image is None:
            raise ValueError(f"Split manifest image is absent from CVAT export: {filename}")
        if not source_path.is_file():
            raise FileNotFoundError(f"Split manifest image is absent locally: {source_path}")
        image_output = output_dir / "images" / destination_split / filename
        label_output = output_dir / "labels" / destination_split / f"{Path(filename).stem}.txt"
        image_output.parent.mkdir(parents=True, exist_ok=True)
        label_output.parent.mkdir(parents=True, exist_ok=True)
        copy_methods[_copy_image(source_path, image_output)] += 1
        normalization_methods[_ensure_terminal_jpeg_eoi(image_output)] += 1
        label_lines = [_format_polygon(polygon.points, image.width, image.height) for polygon in image.polygons]
        label_output.write_text("\n".join(label_lines) + "\n", encoding="utf-8")
        counts[split] += 1
        instances[split] += len(label_lines)
        manifest_rows.append(
            {
                "filename": filename,
                "split": split,
                "image_width": image.width,
                "image_height": image.height,
                "instances": len(label_lines),
                "source_image": str(source_path),
                "derived_image": str(image_output),
                "derived_label": str(label_output),
                "source_image_sha256": _file_sha256(source_path),
                "derived_image_sha256": _file_sha256(image_output),
                "label_sha256": _file_sha256(label_output),
            }
        )

    dataset_yaml = {
        "path": output_dir.as_posix(),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {0: "billet_front_face"},
    }
    (output_dir / "dataset.yaml").write_text(yaml.safe_dump(dataset_yaml, sort_keys=False, allow_unicode=True), encoding="utf-8")
    with (output_dir / "conversion_manifest.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)
    summary = {
        "schema_version": "1.1",
        "source_dataset_version": config["project"]["dataset_version"],
        "source_annotation_version": config["project"]["annotation_version"],
        "source_annotation_sha256": _file_sha256(annotation_xml),
        "source_split_manifest_sha256": _file_sha256(split_manifest),
        "images": dict(counts),
        "instances": dict(instances),
        "copy_methods": dict(copy_methods),
        "derived_image_normalization": dict(normalization_methods),
        "source_images_immutable": True,
        "target_class": "billet_front_face",
        "test_holdout_policy": "DO_NOT_USE_FOR_TUNING",
    }
    (output_dir / "conversion_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert accepted CVAT polygons to a versioned YOLO segmentation dataset.")
    parser.add_argument("--config", type=Path, default=Path("configs/dataset.yaml"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/yolo_seg_v3"))
    args = parser.parse_args()
    print(json.dumps(export_dataset(args.config, args.output), indent=2))


if __name__ == "__main__":
    main()
