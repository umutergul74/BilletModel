from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import argparse
import csv
import hashlib
import json

import yaml

from steel_billet_vision.annotation.cvat import load_cvat_images_xml


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    root = config_path.parent.parent
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    paths = config["paths"]
    output = (root / paths["audit_output"]).resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite incremental dataset audit: {output}")

    def read_csv(relative: str) -> list[dict[str, str]]:
        with (root / relative).resolve().open(encoding="utf-8-sig") as stream:
            return list(csv.DictReader(stream))

    inventory = read_csv(paths["base_inventory"])
    base_splits = read_csv(paths["base_split_manifest"])
    active_rows = read_csv(paths["active_learning_manifest"])
    annotation_xml = (root / paths["annotation_xml"]).resolve()
    export = load_cvat_images_xml(annotation_xml)
    annotation_counts = {image.name: len(image.polygons) for image in export.images}
    inventory_by_name = {row["filename"]: row for row in inventory}
    base_names = {row["filename"] for row in base_splits}
    active_names = {row["filename"] for row in active_rows}
    if base_names & active_names:
        raise ValueError(f"Active-learning images already exist in base split: {sorted(base_names & active_names)}")
    if not active_names <= set(annotation_counts):
        raise ValueError(f"Active-learning images missing from merged annotations: {sorted(active_names - set(annotation_counts))}")

    holdout_groups = {
        row["scene_group"] for row in base_splits if row["split"] in {"validation", "test"}
    }
    active_holdout_overlap = sorted(
        {row["scene_group"] for row in active_rows} & holdout_groups
    )
    if active_holdout_overlap:
        raise ValueError(f"Active-learning scene leakage into holdout: {active_holdout_overlap}")

    split_rows: list[dict[str, Any]] = []
    split_by_name: dict[str, str] = {}
    group_by_name: dict[str, str] = {}
    for row in base_splits:
        name = row["filename"]
        split_by_name[name] = row["split"]
        group_by_name[name] = row["scene_group"]
    new_split = config["dataset"]["new_active_learning_split"]
    for row in active_rows:
        split_by_name[row["filename"]] = new_split
        group_by_name[row["filename"]] = row["scene_group"]

    for name in sorted(split_by_name):
        if name not in inventory_by_name:
            raise FileNotFoundError(f"Trainable image is absent from source inventory: {name}")
        if name not in annotation_counts:
            raise ValueError(f"Trainable image is absent from merged annotations: {name}")
        split_rows.append(
            {
                "filename": name,
                "scene_group": group_by_name[name],
                "split": split_by_name[name],
                "annotation_instances": annotation_counts[name],
                "annotation_version": config["project"]["annotation_version"],
                "dataset_version": config["project"]["dataset_version"],
            }
        )

    split_groups: dict[str, set[str]] = defaultdict(set)
    for row in split_rows:
        split_groups[row["split"]].add(row["scene_group"])
    leakage = {
        f"{left}:{right}": sorted(split_groups[left] & split_groups[right])
        for left in split_groups
        for right in split_groups
        if left < right and split_groups[left] & split_groups[right]
    }
    if leakage:
        raise ValueError(f"Scene groups overlap across splits: {leakage}")

    images_root = (root / paths["images"]).resolve()
    source_hash_mismatches: list[str] = []
    for name in split_by_name:
        actual = _sha256(images_root / name)
        if actual != inventory_by_name[name]["sha256"]:
            source_hash_mismatches.append(name)
    if source_hash_mismatches:
        raise ValueError(f"Trainable source image hashes changed: {source_hash_mismatches}")

    for row in inventory:
        name = row["filename"]
        row["annotation_instances"] = annotation_counts.get(name, 0)
        row["annotation_status"] = "OWNER_ACCEPTED" if name in annotation_counts else "UNLABELED"
        row["split"] = split_by_name.get(name, "unlabeled_pool" if row["readable"] == "True" else "excluded_unreadable")

    output.mkdir(parents=True)
    inventory_fields = sorted({key for row in inventory for key in row})
    with (output / "image_inventory.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=inventory_fields)
        writer.writeheader()
        writer.writerows(inventory)
    with (output / "split_manifest.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(split_rows[0]))
        writer.writeheader()
        writer.writerows(split_rows)

    image_counts = Counter(row["split"] for row in split_rows)
    instance_counts: Counter[str] = Counter()
    for row in split_rows:
        instance_counts[row["split"]] += int(row["annotation_instances"])
    summary = {
        "schema_version": "1.0",
        "dataset_version": config["project"]["dataset_version"],
        "annotation_version": config["project"]["annotation_version"],
        "annotation_xml_sha256": _sha256(annotation_xml),
        "base_split_manifest_sha256": _sha256((root / paths["base_split_manifest"]).resolve()),
        "active_learning_manifest_sha256": _sha256((root / paths["active_learning_manifest"]).resolve()),
        "trainable_images": len(split_rows),
        "trainable_instances": sum(instance_counts.values()),
        "split_image_counts": dict(image_counts),
        "split_instance_counts": dict(instance_counts),
        "split_scene_group_counts": {split: len(groups) for split, groups in split_groups.items()},
        "new_active_learning_images": len(active_names),
        "new_active_learning_instances": sum(annotation_counts[name] for name in active_names),
        "holdout_groups_preserved": sorted(holdout_groups),
        "scene_group_leakage": {},
        "source_hash_mismatches": [],
        "annotated_images_missing_locally": sorted(set(annotation_counts) - set(inventory_by_name)),
        "test_holdout_policy": config["dataset"]["test_holdout_policy"],
    }
    (output / "dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Preserve frozen splits while adding accepted active-learning images to train.")
    parser.add_argument("--config", type=Path, default=Path("configs/dataset_v3_active_learning_round_01.yaml"))
    args = parser.parse_args()
    print(json.dumps(build(args.config), indent=2))


if __name__ == "__main__":
    main()
