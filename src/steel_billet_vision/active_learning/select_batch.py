from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import argparse
import csv
import hashlib
import json
import math
import shutil
import statistics
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import yaml

from steel_billet_vision.data.audit import hamming


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rank_percentiles(values: list[float]) -> list[float]:
    if not values:
        return []
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    denominator = max(1, len(values) - 1)
    for rank, index in enumerate(order):
        ranks[index] = rank / denominator
    return ranks


def _pairwise_iou_fraction(boxes: np.ndarray, threshold: float = 0.05) -> float:
    if len(boxes) < 2:
        return 0.0
    overlaps = 0
    pairs = 0
    for left_index in range(len(boxes)):
        left = boxes[left_index]
        for right in boxes[left_index + 1 :]:
            intersection_width = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
            intersection_height = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
            intersection = intersection_width * intersection_height
            left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
            right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
            union = left_area + right_area - intersection
            overlaps += int(union > 0 and intersection / union >= threshold)
            pairs += 1
    return overlaps / pairs if pairs else 0.0


def _robust_ood_score(row: dict[str, str], accepted: list[dict[str, str]]) -> float:
    features = (
        ("brightness_mean", False),
        ("contrast_std", False),
        ("blur_laplacian_variance", True),
        ("dark_fraction", False),
        ("bright_fraction", False),
        ("aspect_ratio", False),
    )
    deviations: list[float] = []
    for key, use_log in features:
        reference = [math.log1p(float(item[key])) if use_log else float(item[key]) for item in accepted]
        value = math.log1p(float(row[key])) if use_log else float(row[key])
        median = statistics.median(reference)
        mad = statistics.median(abs(item - median) for item in reference)
        deviations.append(min(6.0, abs(value - median) / max(mad * 1.4826, 1e-6)))
    return statistics.mean(deviations)


def _select_diverse(
    records: list[dict[str, Any]],
    target_count: int,
    max_per_scene: int,
    max_zero: int,
    near_duplicate_threshold: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    scene_counts: Counter[str] = Counter()
    zero_count = 0

    def can_add(record: dict[str, Any]) -> bool:
        nonlocal zero_count
        if scene_counts[record["scene_group"]] >= max_per_scene:
            return False
        if record["detection_count_low"] == 0 and zero_count >= max_zero:
            return False
        candidate_hash = int(record["phash_hex"], 16)
        return all(hamming(candidate_hash, int(item["phash_hex"], 16)) > near_duplicate_threshold for item in selected)

    def add(record: dict[str, Any]) -> None:
        nonlocal zero_count
        selected.append(record)
        scene_counts[record["scene_group"]] += 1
        zero_count += int(record["detection_count_low"] == 0)

    by_scene: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_scene[record["scene_group"]].append(record)
    scene_representatives = sorted(
        (max(members, key=lambda item: (item["selection_score"], item["filename"])) for members in by_scene.values()),
        key=lambda item: (-item["selection_score"], item["scene_group"], item["filename"]),
    )
    for record in scene_representatives:
        if len(selected) >= target_count:
            break
        if can_add(record):
            add(record)
    for record in sorted(records, key=lambda item: (-item["selection_score"], item["scene_group"], item["filename"])):
        if len(selected) >= target_count:
            break
        if record not in selected and can_add(record):
            add(record)
    return selected


def _reason(record: dict[str, Any]) -> str:
    reasons: list[str] = []
    if record["detection_count_low"] == 0:
        reasons.append("model_hic_yuz_bulamadi")
    if record["uncertainty_rank"] >= 0.75:
        reasons.append("dusuk_guven")
    if record["count_rank"] >= 0.75:
        reasons.append("kalabalik_sahne")
    if record["small_face_rank"] >= 0.75:
        reasons.append("kucuk_uzak_yuzler")
    if record["crowding_rank"] >= 0.75:
        reasons.append("ortusen_yuzler")
    if record["ood_rank"] >= 0.75:
        reasons.append("aykiri_aydinlatma_netlik_veya_kadraj")
    if record["distance_rank"] >= 0.75:
        reasons.append("mevcut_etiketlerden_gorsel_olarak_uzak")
    return ";".join(reasons[:3]) or "sahne_cesitliligi"


def _write_contact_sheets(selected: list[dict[str, Any]], image_root: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    page_size = 12
    cell_width, cell_height = 360, 300
    columns, rows = 3, 4
    font = ImageFont.load_default()
    for page_index, start in enumerate(range(0, len(selected), page_size), start=1):
        canvas = Image.new("RGB", (columns * cell_width, rows * cell_height), "white")
        draw = ImageDraw.Draw(canvas)
        for local_index, record in enumerate(selected[start : start + page_size]):
            source = image_root / record["filename"]
            with Image.open(source) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((cell_width - 12, cell_height - 52))
                x = (local_index % columns) * cell_width + (cell_width - image.width) // 2
                y = (local_index // columns) * cell_height + 36
                canvas.paste(image, (x, y))
            label = (
                f"{start + local_index + 1:02d} {record['filename']}  "
                f"score={float(record['selection_score']):.3f} "
                f"n={int(record['detection_count_standard'])}"
            )
            draw.text(((local_index % columns) * cell_width + 6, (local_index // columns) * cell_height + 8), label, fill="black", font=font)
        canvas.save(output_dir / f"contact_sheet_{page_index:02d}.jpg", quality=90)


def run(config_path: Path) -> dict[str, Any]:
    from ultralytics import YOLO

    config_path = config_path.resolve()
    root = config_path.parent.parent.parent
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    settings = config["active_learning"]
    inventory_path = (root / config["data"]["inventory"]).resolve()
    image_root = (root / config["data"]["images"]).resolve()
    checkpoint = (root / config["model"]["checkpoint"]).resolve()
    audit_dir = (root / config["output"]["audit_dir"]).resolve()
    batch_dir = (root / config["output"]["annotation_batch_dir"]).resolve()
    for destination in (audit_dir, batch_dir):
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite active-learning output: {destination}")

    with inventory_path.open(encoding="utf-8-sig") as stream:
        inventory = list(csv.DictReader(stream))
    accepted = [row for row in inventory if row["annotation_status"] == "OWNER_ACCEPTED" and row["readable"] == "True"]
    holdout_splits = set(config["data"]["excluded_holdout_splits"])
    holdout_groups = {row["scene_group"] for row in inventory if row["split"] in holdout_splits}
    candidates = [
        row
        for row in inventory
        if row["annotation_status"] == "UNLABELED"
        and row["readable"] == "True"
        and row["scene_group"] not in holdout_groups
    ]

    accepted_hashes = [int(row["phash_hex"], 16) for row in accepted]
    threshold = int(settings["near_duplicate_hamming_threshold"])
    for row in candidates:
        row["min_phash_distance_to_accepted"] = min(hamming(int(row["phash_hex"], 16), value) for value in accepted_hashes)
    inference_candidates = [row for row in candidates if row["min_phash_distance_to_accepted"] > threshold]
    source_hashes_before: dict[str, str] = {}
    for row in inference_candidates:
        path = image_root / row["filename"]
        actual = _sha256(path)
        if actual != row["sha256"]:
            raise ValueError(f"Source hash differs from audited inventory: {path}")
        source_hashes_before[row["filename"]] = actual

    model_settings = config["model"]
    confidence_floor = float(model_settings["confidence_floor"])
    standard_confidence = float(model_settings["standard_confidence"])
    model = YOLO(str(checkpoint))
    paths = [str(image_root / row["filename"]) for row in inference_candidates]
    prediction_by_name: dict[str, dict[str, Any]] = {}
    chunk_size = int(model_settings["source_chunk_size"])
    for start in range(0, len(paths), chunk_size):
        chunk_rows = inference_candidates[start : start + chunk_size]
        results = model.predict(
            source=paths[start : start + chunk_size],
            stream=False,
            imgsz=int(model_settings["image_size"]),
            batch=int(model_settings["batch"]),
            device=model_settings["device"],
            conf=confidence_floor,
            max_det=300,
            save=False,
            verbose=False,
        )
        if len(results) != len(chunk_rows):
            raise RuntimeError("Inference chunk did not return exactly one result per source image")
        for row, result in zip(chunk_rows, results):
            confidences = result.boxes.conf.detach().cpu().numpy() if result.boxes is not None else np.empty(0)
            boxes = result.boxes.xyxyn.detach().cpu().numpy() if result.boxes is not None else np.empty((0, 4))
            xywh = result.boxes.xywhn.detach().cpu().numpy() if result.boxes is not None else np.empty((0, 4))
            standard = confidences >= standard_confidence
            standard_confidences = confidences[standard]
            standard_boxes = boxes[standard]
            standard_areas = xywh[standard, 2] * xywh[standard, 3] if len(xywh) else np.empty(0)
            prediction_by_name[row["filename"]] = {
                "detection_count_low": int(len(confidences)),
                "detection_count_standard": int(standard.sum()),
                "confidence_mean": float(standard_confidences.mean()) if len(standard_confidences) else 0.0,
                "confidence_median": float(np.median(standard_confidences)) if len(standard_confidences) else 0.0,
                "low_confidence_fraction": float(np.mean(confidences < standard_confidence)) if len(confidences) else 1.0,
                "small_face_fraction": float(np.mean(standard_areas < 0.003)) if len(standard_areas) else 1.0,
                "minimum_box_area_fraction": float(standard_areas.min()) if len(standard_areas) else 0.0,
                "crowding_iou_fraction": _pairwise_iou_fraction(standard_boxes),
            }
    if len(prediction_by_name) != len(inference_candidates):
        raise RuntimeError("Inference did not return exactly one result per candidate image")

    records: list[dict[str, Any]] = []
    for row in inference_candidates:
        record: dict[str, Any] = dict(row)
        record.update(prediction_by_name[row["filename"]])
        record["ood_score"] = _robust_ood_score(row, accepted)
        records.append(record)
    rank_fields = {
        "uncertainty_rank": [1.0 - item["confidence_mean"] + item["low_confidence_fraction"] for item in records],
        "count_rank": [float(item["detection_count_standard"]) for item in records],
        "small_face_rank": [item["small_face_fraction"] for item in records],
        "crowding_rank": [item["crowding_iou_fraction"] for item in records],
        "ood_rank": [item["ood_score"] for item in records],
        "distance_rank": [float(item["min_phash_distance_to_accepted"]) for item in records],
    }
    for field, values in rank_fields.items():
        for record, rank in zip(records, _rank_percentiles(values)):
            record[field] = rank
    for record in records:
        record["selection_score"] = (
            0.28 * record["uncertainty_rank"]
            + 0.20 * record["count_rank"]
            + 0.14 * record["small_face_rank"]
            + 0.10 * record["crowding_rank"]
            + 0.16 * record["ood_rank"]
            + 0.12 * record["distance_rank"]
            + (0.08 if record["detection_count_low"] == 0 else 0.0)
        )
        record["selection_reason"] = _reason(record)

    selected = _select_diverse(
        records,
        int(settings["target_count"]),
        int(settings["max_per_scene_group"]),
        int(settings["max_zero_detection_images"]),
        threshold,
    )
    if len(selected) != int(settings["target_count"]):
        raise RuntimeError(f"Could select only {len(selected)} of {settings['target_count']} requested images")

    audit_dir.mkdir(parents=True)
    image_output = batch_dir / "images"
    image_output.mkdir(parents=True)
    ordered_fields = [
        "batch_order",
        "filename",
        "scene_group",
        "selection_score",
        "selection_reason",
        "detection_count_low",
        "detection_count_standard",
        "confidence_mean",
        "confidence_median",
        "low_confidence_fraction",
        "small_face_fraction",
        "minimum_box_area_fraction",
        "crowding_iou_fraction",
        "ood_score",
        "min_phash_distance_to_accepted",
        "brightness_mean",
        "contrast_std",
        "blur_laplacian_variance",
        "dark_fraction",
        "bright_fraction",
        "phash_hex",
        "sha256",
    ]
    with (audit_dir / "candidate_scores.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        fields = sorted({key for record in records for key in record})
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(records, key=lambda item: (-item["selection_score"], item["filename"])))
    manifest_rows: list[dict[str, Any]] = []
    for order, record in enumerate(selected, start=1):
        source = image_root / record["filename"]
        destination = image_output / record["filename"]
        shutil.copy2(source, destination)
        if _sha256(destination) != record["sha256"]:
            raise OSError(f"Annotation-batch copy failed integrity check: {destination}")
        manifest = {field: record.get(field, "") for field in ordered_fields}
        manifest["batch_order"] = order
        manifest_rows.append(manifest)
    for row in inference_candidates:
        if _sha256(image_root / row["filename"]) != source_hashes_before[row["filename"]]:
            raise RuntimeError(f"Source image changed during inference: {row['filename']}")

    for destination in (audit_dir / "selected_manifest.csv", batch_dir / "selected_manifest.csv"):
        with destination.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=ordered_fields)
            writer.writeheader()
            writer.writerows(manifest_rows)
    _write_contact_sheets(selected, image_root, audit_dir / "contact_sheets")
    zip_path = batch_dir / "active_learning_v1_images_for_cvat.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for record in selected:
            archive.write(image_output / record["filename"], arcname=record["filename"])

    summary = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "active_learning_id": settings["id"],
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": _sha256(checkpoint),
        "inventory_sha256": _sha256(inventory_path),
        "unlabeled_images_total": sum(row["annotation_status"] == "UNLABELED" for row in inventory),
        "holdout_scene_groups_excluded": sorted(holdout_groups),
        "holdout_images_excluded": sum(
            row["annotation_status"] == "UNLABELED" and row["scene_group"] in holdout_groups for row in inventory
        ),
        "eligible_before_near_duplicate_filter": len(candidates),
        "eligible_after_near_duplicate_filter": len(inference_candidates),
        "selected_images": len(selected),
        "selected_scene_groups": len({row["scene_group"] for row in selected}),
        "selected_zero_detection_images": sum(row["detection_count_low"] == 0 for row in selected),
        "source_hash_mismatches_after_inference": 0,
        "cvat_zip": str(zip_path),
        "cvat_zip_sha256": _sha256(zip_path),
        "human_review_status": "REQUIRED_BEFORE_ANNOTATION_IMPORT",
        "preannotations_included": False,
    }
    (audit_dir / "selection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (batch_dir / "README.txt").write_text(
        "CVAT active-learning batch v1\n"
        "\n"
        "Target label: billet_front_face\n"
        "Annotate only physically visible front-face pixels.\n"
        "Do not complete hidden regions, force four corners, or include side surfaces.\n"
        "Shadowed but visible pixels remain part of the mask.\n"
        "This package contains images only; baseline predictions are not ground truth.\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Select and package a leakage-safe active-learning annotation batch.")
    parser.add_argument("--config", type=Path, default=Path("configs/active_learning/batch_v1.yaml"))
    args = parser.parse_args()
    print(json.dumps(run(args.config), indent=2))


if __name__ == "__main__":
    main()
