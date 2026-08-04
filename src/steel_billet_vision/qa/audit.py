from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import argparse
import csv
import hashlib
import json

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import yaml

from steel_billet_vision.annotation.cvat import CvatImage, load_cvat_images_xml
from steel_billet_vision.qa.geometry import (
    area,
    has_duplicate_vertices,
    has_out_of_bounds_vertex,
    is_concave,
    is_self_intersecting,
    touches_frame,
)
from steel_billet_vision.visualization.overlay import render_overlay, write_review_html


def _write_overlay_contact_sheets(image_records: list[dict[str, Any]], output_dir: Path) -> None:
    contact_dir = output_dir / "contact_sheets"
    contact_dir.mkdir(parents=True, exist_ok=True)
    page_size = 9
    columns = 3
    cell_width, cell_height = 540, 500
    font = ImageFont.load_default()
    available = [record for record in image_records if record["overlay_href"]]
    for page_index, start in enumerate(range(0, len(available), page_size), start=1):
        page_records = available[start : start + page_size]
        rows = (len(page_records) + columns - 1) // columns
        canvas = Image.new("RGB", (columns * cell_width, rows * cell_height), "white")
        draw = ImageDraw.Draw(canvas)
        for local_index, record in enumerate(page_records):
            overlay_path = output_dir / record["overlay_href"]
            with Image.open(overlay_path) as image:
                image = image.convert("RGB")
                image.thumbnail((cell_width - 16, cell_height - 52))
                x = (local_index % columns) * cell_width + (cell_width - image.width) // 2
                y = (local_index // columns) * cell_height + 42
                canvas.paste(image, (x, y))
            label = (
                f"id={record['image_id']} {record['name']} "
                f"instances={len(record['instances'])}"
            )
            draw.text(
                ((local_index % columns) * cell_width + 8, (local_index // columns) * cell_height + 10),
                label,
                fill="black",
                font=font,
            )
        canvas.save(contact_dir / f"contact_sheet_{page_index:02d}.jpg", quality=90)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pairwise_overlap_signals(image: CvatImage, scale: float, overlap_threshold: float, duplicate_iou: float) -> dict[int, list[str]]:
    width = max(1, round(image.width * scale))
    height = max(1, round(image.height * scale))
    masks: list[np.ndarray] = []
    mask_areas: list[int] = []
    for polygon in image.polygons:
        mask = np.zeros((height, width), dtype=np.uint8)
        pts = np.round(np.asarray(polygon.points, np.float32) * scale).astype(np.int32)
        cv2.fillPoly(mask, [pts], 1)
        masks.append(mask)
        mask_areas.append(int(mask.sum()))
    result: dict[int, list[str]] = {p.instance_index: [] for p in image.polygons}
    for i in range(len(masks)):
        for j in range(i + 1, len(masks)):
            intersection = int(np.count_nonzero(masks[i] & masks[j]))
            if not intersection:
                continue
            smaller = min(mask_areas[i], mask_areas[j])
            union = mask_areas[i] + mask_areas[j] - intersection
            ios = intersection / smaller if smaller else 0.0
            iou = intersection / union if union else 0.0
            left = image.polygons[i].instance_index
            right = image.polygons[j].instance_index
            if iou >= duplicate_iou:
                result[left].append(f"LIKELY_DUPLICATE_INSTANCE:{right}")
                result[right].append(f"LIKELY_DUPLICATE_INSTANCE:{left}")
            elif ios >= overlap_threshold:
                result[left].append(f"POLYGON_OVERLAP_REVIEW:{right}")
                result[right].append(f"POLYGON_OVERLAP_REVIEW:{left}")
    return result


def _audit_instance(image: CvatImage, polygon: Any, config: dict[str, Any]) -> dict[str, Any]:
    points = list(polygon.points)
    vertex_count = len(points)
    polygon_area = area(points)
    area_ratio = polygon_area / (image.width * image.height)
    accepted = config.get("annotation_status") == "OWNER_ACCEPTED"
    signals: list[str] = [] if accepted else ["UNVERIFIED_HUMAN_ANNOTATION"]
    if vertex_count == 3:
        signals.append("TRIANGULAR_VISIBLE_REGION_REVIEW")
    elif vertex_count > 4:
        signals.append("MULTISIDED_VISIBLE_REGION_REVIEW")
    if is_concave(points):
        signals.append("CONCAVE_VISIBLE_REGION_REVIEW")
    if touches_frame(points, image.width, image.height, float(config["boundary_tolerance_px"])):
        signals.append("FRAME_BOUNDARY_TRUNCATION_REVIEW")
    if has_duplicate_vertices(points):
        signals.append("DUPLICATE_VERTEX")
    if is_self_intersecting(points):
        signals.append("SELF_INTERSECTION")
    if has_out_of_bounds_vertex(points, image.width, image.height):
        signals.append("OUT_OF_BOUNDS_VERTEX")
    if area_ratio < float(config["very_small_area_ratio"]):
        signals.append("VERY_SMALL_MASK_REVIEW")
    if polygon.label != config["target_label"]:
        signals.append("UNEXPECTED_CLASS")
    return {
        "stable_id": f"image-{image.image_id:04d}-instance-{polygon.instance_index:03d}",
        "instance_index": polygon.instance_index,
        "label": polygon.label,
        "source": polygon.source,
        "occluded_attribute": polygon.occluded,
        "z_order": polygon.z_order,
        "vertex_count": vertex_count,
        "points": [[x, y] for x, y in points],
        "area_px2": polygon_area,
        "area_ratio": area_ratio,
        "signals": signals,
        "automated_quality": "OWNER_ACCEPTED" if accepted else "REVIEW_REQUIRED",
        "human_decision": "OWNER_ACCEPTED" if accepted else None,
    }


def _review_guidance(signals: list[str]) -> tuple[str, str, str]:
    structural = {"SELF_INTERSECTION", "DUPLICATE_VERTEX", "OUT_OF_BOUNDS_VERTEX"}
    if "MISSING_SOURCE_IMAGE" in signals:
        return (
            "P0",
            "Kaynak görüntü bulunamadığı için maskenin görsel doğruluğu değerlendirilemiyor.",
            "Aynı kaynak görüntüyü geri yükleyin, boyutunu/sahneyi doğrulayın ve sonra CVAT'ta inceleyin. Görüntü gelmeden onaylamayın.",
        )
    if structural.intersection(signals):
        return (
            "P1",
            "Polygon yapısında geçerlilik uyarısı var; gerçek bir etiketleme hatası olabilir.",
            "Noktaları CVAT'ta inceleyin. Görünen fiziksel sınırı koruyarak tekrarlanan veya kesişen hatalı noktaları düzeltin.",
        )
    if "VERY_SMALL_MASK_REVIEW" in signals:
        return (
            "P1",
            "Maske alışılmadık derecede küçük; geçerli bir aşırı örtüşme veya yanlışlıkla çizilmiş bir parça olabilir.",
            "Fiziksel olarak tanımlanabilir bir ön yüz bölgesi olup olmadığına karar verin. Güvenilir değilse BELİRSİZ veya GEÇERSİZ seçin.",
        )
    if any(s.startswith("LIKELY_DUPLICATE_INSTANCE") or s.startswith("POLYGON_OVERLAP_REVIEW") for s in signals):
        return (
            "P1",
            "İki maske önemli ölçüde çakışıyor veya aynı fiziksel billet'i temsil ediyor olabilir.",
            "İki instance'ı CVAT'ta birlikte inceleyin; yalnızca fiziksel olarak ayrıysa ikisini de tutun.",
        )
    if any(s in signals for s in ("TRIANGULAR_VISIBLE_REGION_REVIEW", "MULTISIDED_VISIBLE_REGION_REVIEW", "CONCAVE_VISIBLE_REGION_REVIEW", "FRAME_BOUNDARY_TRUNCATION_REVIEW")):
        return (
            "P2",
            "Şekil veya görüntü sınırında kesilme fiziksel olarak yorumlanmalı; köşe sayısı tek başına hata değildir.",
            "Polygonun yalnızca görünen ön yüzü izlediğini, örtücü nesnede/görüntü kenarında durduğunu ve gizli geometri uydurmadığını doğrulayın.",
        )
    return (
        "P3",
        "Bu insan çizimi polygon, görünür ön yüz kurallarına göre henüz doğrulanmadı.",
        "Ön yüz kapsamını, yan yüzlerin dışarıda kalmasını, gölge/örtüşme sınırını ve çizim hassasiyetini kontrol edip insan kararını kaydedin.",
    )


def run(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    project_root = config_path.parent.parent
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    paths = config["paths"]
    images_dir = (project_root / paths["images"]).resolve()
    xml_path = (project_root / paths["annotation_xml"]).resolve()
    output_dir = (project_root / paths["output"]).resolve()
    overlays_dir = output_dir / "overlays"
    output_dir.mkdir(parents=True, exist_ok=True)

    export = load_cvat_images_xml(xml_path)
    qa_config = dict(config["qa"])
    qa_config["annotation_status"] = config["project"]["annotation_status"]
    image_records: list[dict[str, Any]] = []
    signal_counts: Counter[str] = Counter()
    vertex_counts: Counter[int] = Counter()
    source_hashes: dict[str, str] = {}
    annotated_present = 0
    for image in export.images:
        source_path = images_dir / image.name
        source_exists = source_path.is_file()
        instances = [_audit_instance(image, polygon, qa_config) for polygon in image.polygons]
        overlap = _pairwise_overlap_signals(
            image,
            float(config["qa"]["raster_scale"]),
            float(config["qa"]["overlap_intersection_over_smaller"]),
            float(config["qa"]["likely_duplicate_iou"]),
        )
        for instance in instances:
            instance["signals"].extend(overlap[instance["instance_index"]])
            if not source_exists:
                instance["signals"].append("MISSING_SOURCE_IMAGE")
            instance["signals"] = sorted(set(instance["signals"]))
            priority, likely_issue, decision_required = _review_guidance(instance["signals"])
            instance["review_priority"] = priority
            instance["likely_issue"] = likely_issue
            instance["decision_required"] = decision_required
            signal_counts.update(instance["signals"])
            vertex_counts[instance["vertex_count"]] += 1
        if source_exists:
            source_hashes[image.name] = _sha256(source_path)
            if instances:
                annotated_present += 1
            overlay_path = overlays_dir / f"{image.image_id:04d}_{Path(image.name).stem}.jpg"
            render_overlay(source_path, instances, overlay_path, int(config["qa"]["overlay_max_dimension"]))
            overlay_href = overlay_path.relative_to(output_dir).as_posix()
            source_href = Path("../..") / image.name
            source_href = source_href.as_posix()
        else:
            overlay_href = ""
            source_href = ""
        image_records.append(
            {
                "image_id": image.image_id,
                "name": image.name,
                "width": image.width,
                "height": image.height,
                "source_exists": source_exists,
                "source_href": source_href,
                "source_sha256": source_hashes.get(image.name),
                "overlay_href": overlay_href,
                "instances": instances,
                "automated_image_quality": "REVIEW_REQUIRED" if instances else "EMPTY_FRAME_REVIEW_REQUIRED",
            }
        )

    summary = {
        "schema_version": "1.0",
        "generated_by": "steel_billet_vision.qa.audit",
        "annotation_version": config["project"]["annotation_version"],
        "annotation_status": config["project"]["annotation_status"],
        "dataset_version": config["project"]["dataset_version"],
        "cvat_format_version": export.format_version,
        "cvat_metadata": export.metadata,
        "label_schema": list(export.labels),
        "job_frames_total": len(export.images),
        "annotated_frames_total": sum(bool(image.polygons) for image in export.images),
        "empty_frames_total": sum(not image.polygons for image in export.images),
        "source_images_present": sum(record["source_exists"] for record in image_records),
        "source_images_missing": sum(not record["source_exists"] for record in image_records),
        "annotated_source_images_present": annotated_present,
        "instances_total": sum(len(image.polygons) for image in export.images),
        "vertex_count_distribution": dict(sorted(vertex_counts.items())),
        "signal_counts": dict(signal_counts.most_common()),
        "automated_scope_limitations": [
            "Side-face inclusion, hidden-geometry completion, shadow-vs-occlusion, and missing billets require visual human judgment.",
            "Topology signals (triangle, multi-sided, concave, truncated) are not automatic errors.",
            (
                "The dataset owner accepted remaining visual-boundary ambiguity; topology signals remain documented but do not revoke that decision."
                if config["project"]["annotation_status"] == "OWNER_ACCEPTED"
                else "No annotation was modified; every polygon remains UNVERIFIED until a human decision is recorded."
            ),
        ],
    }
    report = {"summary": summary, "images": image_records}
    (output_dir / "annotation_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    with (output_dir / "review_queue.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["review_priority", "stable_id", "image_id", "image_name", "instance_index", "vertex_count", "area_ratio", "signals", "likely_issue", "decision_required", "human_decision"])
        writer.writeheader()
        for image in image_records:
            for instance in image["instances"]:
                writer.writerow(
                    {
                        "review_priority": instance["review_priority"],
                        "stable_id": instance["stable_id"],
                        "image_id": image["image_id"],
                        "image_name": image["name"],
                        "instance_index": instance["instance_index"],
                        "vertex_count": instance["vertex_count"],
                        "area_ratio": f"{instance['area_ratio']:.8f}",
                        "signals": "|".join(instance["signals"]),
                        "likely_issue": instance["likely_issue"],
                        "decision_required": instance["decision_required"],
                        "human_decision": "",
                    }
                )
    with (output_dir / "image_review_queue.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["image_id", "image_name", "source_exists", "instance_count", "image_status", "decision_required"])
        writer.writeheader()
        for image in image_records:
            if not image["source_exists"]:
                decision = "Restore the exact source image before visual verification."
            elif not image["instances"]:
                decision = "Confirm in CVAT whether this is intentionally empty or contains missing billet_front_face instances."
            else:
                decision = "Confirm all visible billets are represented and no side surfaces/background/hidden geometry are included."
            writer.writerow({
                "image_id": image["image_id"], "image_name": image["name"], "source_exists": image["source_exists"],
                "instance_count": len(image["instances"]), "image_status": image["automated_image_quality"], "decision_required": decision,
            })
    write_review_html(report, output_dir / "review.html")
    _write_overlay_contact_sheets(image_records, output_dir)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit CVAT visible-front-face polygons without modifying annotations.")
    parser.add_argument("--config", type=Path, default=Path("configs/annotation_qa.yaml"))
    args = parser.parse_args()
    report = run(args.config)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
