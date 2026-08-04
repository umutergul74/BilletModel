from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import argparse
import csv
import json
import shutil
import zipfile

import yaml

from steel_billet_vision.active_learning.select_batch import _sha256, _write_contact_sheets
from steel_billet_vision.data.audit import hamming


def _adjusted_score(record: dict[str, Any], soft_limit: int, penalty: float) -> float:
    excess = max(0, int(record["detection_count_standard"]) - soft_limit)
    return float(record["selection_score"]) - penalty * excess


def select_scene_representatives(
    records: list[dict[str, Any]],
    soft_limit: int,
    penalty: float,
    near_duplicate_threshold: int,
) -> list[dict[str, Any]]:
    """Choose one useful, workload-aware and non-duplicate image from every scene."""
    by_scene: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        record["workload_adjusted_score"] = _adjusted_score(record, soft_limit, penalty)
        by_scene[record["scene_group"]].append(record)

    scene_order = sorted(
        by_scene,
        key=lambda scene: (
            -max(float(item["workload_adjusted_score"]) for item in by_scene[scene]),
            scene,
        ),
    )
    selected: list[dict[str, Any]] = []
    for scene in scene_order:
        ranked = sorted(
            by_scene[scene],
            key=lambda item: (-float(item["workload_adjusted_score"]), item["filename"]),
        )
        for record in ranked:
            candidate_hash = int(record["phash_hex"], 16)
            if all(
                hamming(candidate_hash, int(existing["phash_hex"], 16)) > near_duplicate_threshold
                for existing in selected
            ):
                selected.append(record)
                break
        else:
            raise RuntimeError(f"No non-duplicate representative remains for scene {scene}")
    return selected


def run(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    root = config_path.parent.parent.parent
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    settings = config["curation"]
    candidate_path = (root / config["data"]["candidate_scores"]).resolve()
    inventory_path = (root / config["data"]["inventory"]).resolve()
    image_root = (root / config["data"]["images"]).resolve()
    audit_dir = (root / config["output"]["audit_dir"]).resolve()
    batch_dir = (root / config["output"]["annotation_batch_dir"]).resolve()
    for destination in (audit_dir, batch_dir):
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite curated output: {destination}")

    with candidate_path.open(encoding="utf-8-sig") as stream:
        records: list[dict[str, Any]] = list(csv.DictReader(stream))
    with inventory_path.open(encoding="utf-8-sig") as stream:
        inventory = list(csv.DictReader(stream))
    inventory_by_name = {row["filename"]: row for row in inventory}
    holdout_splits = set(config["data"]["excluded_holdout_splits"])
    holdout_groups = {row["scene_group"] for row in inventory if row["split"] in holdout_splits}
    if any(row["scene_group"] in holdout_groups for row in records):
        raise ValueError("Candidate cache contains a validation/test scene group")

    selected = select_scene_representatives(
        records,
        int(settings["annotation_effort_soft_limit"]),
        float(settings["annotation_effort_penalty_per_detection"]),
        int(settings["near_duplicate_hamming_threshold"]),
    )
    target_count = int(settings["target_count"])
    if len(selected) != target_count:
        raise RuntimeError(
            f"Expected one image from each of {target_count} scenes, selected {len(selected)}"
        )

    audit_dir.mkdir(parents=True)
    image_output = batch_dir / "images"
    image_output.mkdir(parents=True)
    manifest_fields = [
        "batch_order",
        "filename",
        "scene_group",
        "selection_score",
        "workload_adjusted_score",
        "selection_reason",
        "detection_count_low",
        "detection_count_standard",
        "phash_hex",
        "sha256",
    ]
    manifest_rows: list[dict[str, Any]] = []
    for order, record in enumerate(selected, start=1):
        inventory_row = inventory_by_name.get(record["filename"])
        if inventory_row is None or inventory_row["annotation_status"] != "UNLABELED":
            raise ValueError(f"Selected image is not currently UNLABELED: {record['filename']}")
        source = image_root / record["filename"]
        source_hash = _sha256(source)
        if source_hash != record["sha256"] or source_hash != inventory_row["sha256"]:
            raise ValueError(f"Source integrity check failed: {source}")
        destination = image_output / record["filename"]
        shutil.copy2(source, destination)
        if _sha256(destination) != source_hash:
            raise OSError(f"Curated image copy failed integrity check: {destination}")
        row = {field: record.get(field, "") for field in manifest_fields}
        row["batch_order"] = order
        manifest_rows.append(row)

    for destination in (audit_dir / "selected_manifest.csv", batch_dir / "selected_manifest.csv"):
        with destination.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=manifest_fields)
            writer.writeheader()
            writer.writerows(manifest_rows)

    _write_contact_sheets(selected, image_root, audit_dir / "contact_sheets")
    zip_path = batch_dir / config["output"]["zip_name"]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for record in selected:
            archive.write(image_output / record["filename"], arcname=record["filename"])

    selected_instances = sum(int(row["detection_count_standard"]) for row in selected)
    summary = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "active_learning_id": settings["id"],
        "source_candidate_scores": str(candidate_path),
        "source_candidate_scores_sha256": _sha256(candidate_path),
        "inventory_sha256": _sha256(inventory_path),
        "selected_images": len(selected),
        "selected_scene_groups": len({row["scene_group"] for row in selected}),
        "estimated_instances_at_confidence_0_25": selected_instances,
        "holdout_scene_groups_excluded": sorted(holdout_groups),
        "source_hash_mismatches": 0,
        "cvat_zip": str(zip_path),
        "cvat_zip_sha256": _sha256(zip_path),
        "preannotations_included": False,
        "human_annotation_status": "REQUIRED",
    }
    (audit_dir / "selection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (batch_dir / "README.txt").write_text(
        "CVAT aktif öğrenme - 1. tur\n\n"
        "Görevde oluşturulacak tek etiket: billet_front_face\n"
        "Etiket türü: polygon (her görünür ön yüz ayrı bir nesne)\n\n"
        "Yalnızca fiziksel olarak görünen ön-yüz piksellerini çizin.\n"
        "Yan yüzeyleri, gizli kısımları veya görüntü dışını maskeye eklemeyin.\n"
        "Gölgede kalan fakat fiziksel olarak görünen ön-yüz pikselleri maskeye dahildir.\n"
        "Poligonu dört köşeye zorlamayın; fiziksel sınır kaç köşe gerektiriyorsa onu kullanın.\n"
        "Bir görüntüde gerçekten görünür ön yüz yoksa görüntüyü etiketsiz bırakın.\n\n"
        "ZIP yalnızca görüntü içerir. Model tahminleri, insanı yönlendirmemesi için eklenmemiştir.\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the workload-aware CVAT batch from cached active-learning scores.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/active_learning/batch_v1_curated.yaml"),
    )
    args = parser.parse_args()
    print(json.dumps(run(args.config), indent=2))


if __name__ == "__main__":
    main()
