from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import argparse
import csv
import hashlib
import json
import random
import re

import cv2
import numpy as np
import yaml

from steel_billet_vision.annotation.cvat import load_cvat_images_xml


TIMESTAMP_PATTERN = re.compile(r"^(\d{8})_(\d{6})")


class UnionFind:
    def __init__(self, items: list[str]) -> None:
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            parent = self.parent[item]
            self.parent[item] = root
            item = parent
        return root

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def parse_capture_time(filename: str) -> datetime | None:
    match = TIMESTAMP_PATTERN.match(filename)
    if not match:
        return None
    return datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_image(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("OpenCV could not decode the image")
    return image


def _perceptual_hash(gray: np.ndarray) -> int:
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(small)[:8, :8]
    values = dct.flatten()[1:]
    median = float(np.median(values))
    result = 0
    for index, value in enumerate(values):
        if value > median:
            result |= 1 << index
    return result


def inspect_image(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "capture_time": parse_capture_time(path.name).isoformat() if parse_capture_time(path.name) else None,
        "readable": False,
        "error": None,
    }
    try:
        image = _read_image(path)
        height, width = image.shape[:2]
        scale = min(1.0, 1024.0 / max(width, height))
        sample = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA) if scale < 1.0 else image
        gray = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
        result.update(
            {
                "readable": True,
                "width": width,
                "height": height,
                "channels": image.shape[2] if image.ndim == 3 else 1,
                "aspect_ratio": width / height,
                "brightness_mean": float(gray.mean()),
                "contrast_std": float(gray.std()),
                "blur_laplacian_variance": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
                "dark_fraction": float(np.mean(gray <= 15)),
                "bright_fraction": float(np.mean(gray >= 240)),
                "phash_hex": f"{_perceptual_hash(gray):016x}",
            }
        )
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    return result


def _assign_splits(group_members: dict[str, list[str]], ratios: dict[str, float], seed: int) -> dict[str, str]:
    rng = random.Random(seed)
    groups = list(group_members)
    rng.shuffle(groups)
    groups.sort(key=lambda group: len(group_members[group]), reverse=True)
    total = sum(len(group_members[group]) for group in groups)
    targets = {split: total * ratio for split, ratio in ratios.items()}
    counts = {split: 0 for split in ratios}
    assignment: dict[str, str] = {}
    for group in groups:
        size = len(group_members[group])
        split = max(ratios, key=lambda name: (targets[name] - counts[name]) / max(targets[name], 1.0))
        assignment[group] = split
        counts[split] += size
    return assignment


def run(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    root = config_path.parent.parent
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    images_dir = (root / config["paths"]["images"]).resolve()
    output = (root / config["paths"]["audit_output"]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    extensions = {item.lower() for item in config["dataset"]["image_extensions"]}
    paths = sorted(path for path in images_dir.iterdir() if path.is_file() and path.suffix.lower() in extensions)

    records = [inspect_image(path) for path in paths]
    readable = [record for record in records if record["readable"]]
    by_name = {record["filename"]: record for record in records}

    export = load_cvat_images_xml(root / config["paths"]["annotation_xml"])
    annotation_counts = {image.name: len(image.polygons) for image in export.images}
    for record in records:
        record["annotation_instances"] = annotation_counts.get(record["filename"], 0)
        record["annotation_status"] = "OWNER_ACCEPTED" if record["filename"] in annotation_counts else "UNLABELED"

    exact_groups: dict[str, list[str]] = defaultdict(list)
    for record in readable:
        exact_groups[record["sha256"]].append(record["filename"])
    exact_duplicates = [sorted(group) for group in exact_groups.values() if len(group) > 1]

    threshold = int(config["dataset"]["near_duplicate_hamming_threshold"])
    near_pairs: list[dict[str, Any]] = []
    for index, left in enumerate(readable):
        left_hash = int(left["phash_hex"], 16)
        for right in readable[index + 1 :]:
            if left["width"] != right["width"] or left["height"] != right["height"]:
                continue
            distance = hamming(left_hash, int(right["phash_hex"], 16))
            if distance <= threshold and left["sha256"] != right["sha256"]:
                near_pairs.append({"left": left["filename"], "right": right["filename"], "phash_distance": distance})

    names = [record["filename"] for record in readable]
    groups = UnionFind(names)
    for duplicate_group in exact_duplicates:
        for other in duplicate_group[1:]:
            groups.union(duplicate_group[0], other)
    for pair in near_pairs:
        groups.union(pair["left"], pair["right"])
    timed = sorted((parse_capture_time(name), name) for name in names if parse_capture_time(name) is not None)
    gap_seconds = int(config["dataset"]["capture_gap_seconds"])
    for (left_time, left), (right_time, right) in zip(timed, timed[1:]):
        if (right_time - left_time).total_seconds() <= gap_seconds:
            groups.union(left, right)

    grouped: dict[str, list[str]] = defaultdict(list)
    for name in names:
        grouped[groups.find(name)].append(name)
    ordered_groups = sorted((sorted(members) for members in grouped.values()), key=lambda members: members[0])
    group_id_by_name: dict[str, str] = {}
    for index, members in enumerate(ordered_groups, start=1):
        group_id = f"scene-{index:04d}"
        for name in members:
            group_id_by_name[name] = group_id

    annotated_present = sorted(set(annotation_counts) & set(by_name))
    annotated_groups: dict[str, list[str]] = defaultdict(list)
    for name in annotated_present:
        annotated_groups[group_id_by_name[name]].append(name)
    split_assignment = _assign_splits(
        annotated_groups,
        config["dataset"]["split_ratios"],
        int(config["project"]["random_seed"]),
    )
    split_by_name = {name: split_assignment[group_id_by_name[name]] for name in annotated_present}

    for record in records:
        record["scene_group"] = group_id_by_name.get(record["filename"])
        record["split"] = split_by_name.get(record["filename"], "unlabeled_pool" if record["readable"] else "excluded_unreadable")

    fieldnames = sorted({key for record in records for key in record})
    with (output / "image_inventory.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    with (output / "near_duplicate_pairs.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["left", "right", "phash_distance"])
        writer.writeheader()
        writer.writerows(near_pairs)
    with (output / "scene_groups.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["scene_group", "filename", "annotation_status", "split"])
        for record in records:
            writer.writerow([record.get("scene_group"), record["filename"], record["annotation_status"], record["split"]])
    with (output / "split_manifest.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["filename", "scene_group", "split", "annotation_instances", "annotation_version", "dataset_version"])
        for name in annotated_present:
            writer.writerow([name, group_id_by_name[name], split_by_name[name], annotation_counts[name], config["project"]["annotation_version"], config["project"]["dataset_version"]])

    split_counts = defaultdict(int)
    split_group_counts: dict[str, set[str]] = defaultdict(set)
    for name, split in split_by_name.items():
        split_counts[split] += 1
        split_group_counts[split].add(group_id_by_name[name])
    dimensions = defaultdict(int)
    for record in readable:
        dimensions[f"{record['width']}x{record['height']}"] += 1
    summary = {
        "schema_version": "1.0",
        "dataset_version": config["project"]["dataset_version"],
        "annotation_version": config["project"]["annotation_version"],
        "random_seed": config["project"]["random_seed"],
        "images_total": len(records),
        "readable_images": len(readable),
        "unreadable_images": len(records) - len(readable),
        "dimensions": dict(sorted(dimensions.items(), key=lambda item: (-item[1], item[0]))),
        "exact_duplicate_groups": len(exact_duplicates),
        "exact_duplicate_images": sum(len(group) for group in exact_duplicates),
        "near_duplicate_pairs": len(near_pairs),
        "scene_groups": len(ordered_groups),
        "exported_annotated_images": len(annotation_counts),
        "annotated_images_present": len(annotated_present),
        "annotated_images_missing": sorted(set(annotation_counts) - set(by_name)),
        "accepted_instances_total": sum(annotation_counts.values()),
        "trainable_instances_present": sum(annotation_counts[name] for name in annotated_present),
        "split_image_counts": dict(split_counts),
        "split_scene_group_counts": {split: len(groups_) for split, groups_ in split_group_counts.items()},
        "near_duplicate_threshold": threshold,
        "capture_gap_seconds": gap_seconds,
    }
    (output / "dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output / "exact_duplicates.json").write_text(json.dumps(exact_duplicates, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and leakage-group the steel billet image dataset.")
    parser.add_argument("--config", type=Path, default=Path("configs/dataset.yaml"))
    args = parser.parse_args()
    print(json.dumps(run(args.config), indent=2))


if __name__ == "__main__":
    main()

