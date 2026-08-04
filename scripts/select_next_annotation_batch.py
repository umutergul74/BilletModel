from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import argparse
import csv
import math
import statistics

from steel_billet_vision.data.audit import hamming


def main() -> None:
    parser = argparse.ArgumentParser(description="Select a scene-diverse next annotation batch from the audited unlabeled pool.")
    parser.add_argument("--inventory", type=Path, default=Path("outputs/dataset_audit_v2/image_inventory.csv"))
    parser.add_argument("--output", type=Path, default=Path("outputs/dataset_audit_v2/next_annotation_batch.csv"))
    parser.add_argument("--count", type=int, default=30)
    args = parser.parse_args()
    with args.inventory.open(encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    readable = [row for row in rows if row["readable"] == "True"]
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in readable:
        groups[row["scene_group"]].append(row)
    unlabeled_groups = {
        group: members
        for group, members in groups.items()
        if not any(member["annotation_status"] == "OWNER_ACCEPTED" for member in members)
    }
    brightness_median = statistics.median(float(row["brightness_mean"]) for row in readable)
    blur_log_median = statistics.median(math.log1p(float(row["blur_laplacian_variance"])) for row in readable)

    def representative_score(row: dict[str, str]) -> float:
        return abs(float(row["brightness_mean"]) - brightness_median) / 30.0 + abs(math.log1p(float(row["blur_laplacian_variance"])) - blur_log_median)

    selected: list[tuple[dict[str, str], str, int]] = []
    first_by_group: dict[str, dict[str, str]] = {}
    for group, members in sorted(unlabeled_groups.items()):
        first = min(members, key=lambda row: (representative_score(row), row["filename"]))
        first_by_group[group] = first
        selected.append((first, "Her etiketsiz sahne grubundan bir temsilci", len(members)))

    remaining = max(0, args.count - len(selected))
    for group, members in sorted(unlabeled_groups.items(), key=lambda item: (-len(item[1]), item[0])):
        if remaining == 0:
            break
        first = first_by_group[group]
        alternatives = [row for row in members if row["filename"] != first["filename"]]
        if not alternatives:
            continue
        first_hash = int(first["phash_hex"], 16)
        second = max(
            alternatives,
            key=lambda row: (hamming(first_hash, int(row["phash_hex"], 16)), -representative_score(row), row["filename"]),
        )
        selected.append((second, "Büyük sahne grubunda görünüm çeşitliliği için ikinci örnek", len(members)))
        remaining -= 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["batch_order", "filename", "scene_group", "scene_group_size", "selection_reason", "width", "height", "brightness_mean", "blur_laplacian_variance"],
        )
        writer.writeheader()
        for index, (row, reason, group_size) in enumerate(selected[: args.count], start=1):
            writer.writerow(
                {
                    "batch_order": index,
                    "filename": row["filename"],
                    "scene_group": row["scene_group"],
                    "scene_group_size": group_size,
                    "selection_reason": reason,
                    "width": row["width"],
                    "height": row["height"],
                    "brightness_mean": row["brightness_mean"],
                    "blur_laplacian_variance": row["blur_laplacian_variance"],
                }
            )
    print(f"selected {min(len(selected), args.count)} images across {len(unlabeled_groups)} unlabeled-only scene groups")


if __name__ == "__main__":
    main()

