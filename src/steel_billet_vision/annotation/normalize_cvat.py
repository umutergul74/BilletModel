from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET

from steel_billet_vision.annotation.cvat import load_cvat_images_xml


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_consecutive_duplicate_vertices(source_xml: Path, output_xml: Path) -> dict[str, object]:
    source_xml = source_xml.resolve()
    output_xml = output_xml.resolve()
    if output_xml.exists():
        raise FileExistsError(f"Refusing to overwrite normalized annotation XML: {output_xml}")

    before = load_cvat_images_xml(source_xml)
    tree = ET.parse(source_xml)
    root = tree.getroot()
    corrections: list[dict[str, object]] = []
    for image_node in root.findall("image"):
        for instance_index, polygon_node in enumerate(image_node.findall("polygon"), start=1):
            tokens = [token.strip() for token in polygon_node.attrib.get("points", "").split(";") if token.strip()]
            cleaned: list[str] = []
            removed: list[str] = []
            for token in tokens:
                if cleaned and token == cleaned[-1]:
                    removed.append(token)
                else:
                    cleaned.append(token)
            if removed:
                if len(cleaned) < 3:
                    raise ValueError(
                        f"Normalization would leave fewer than three points: {image_node.attrib.get('name')} instance {instance_index}"
                    )
                polygon_node.set("points", ";".join(cleaned))
                corrections.append(
                    {
                        "image_id": int(image_node.attrib["id"]),
                        "image_name": image_node.attrib["name"],
                        "instance_index": instance_index,
                        "removed_consecutive_points": removed,
                    }
                )

    output_xml.parent.mkdir(parents=True, exist_ok=False)
    ET.indent(tree, space="  ")
    tree.write(output_xml, encoding="utf-8", xml_declaration=True)
    after = load_cvat_images_xml(output_xml)
    before_instances = sum(len(image.polygons) for image in before.images)
    after_instances = sum(len(image.polygons) for image in after.images)
    if len(before.images) != len(after.images) or before_instances != after_instances:
        raise RuntimeError("Normalization changed image or instance counts")

    return {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "operation": "REMOVE_EXACT_CONSECUTIVE_DUPLICATE_VERTICES",
        "source_xml": str(source_xml),
        "source_xml_sha256": _sha256(source_xml),
        "output_xml": str(output_xml),
        "output_xml_sha256": _sha256(output_xml),
        "image_count_before_after": [len(before.images), len(after.images)],
        "instance_count_before_after": [before_instances, after_instances],
        "removed_vertex_count": sum(len(item["removed_consecutive_points"]) for item in corrections),
        "corrections": corrections,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a traceable CVAT XML with exact consecutive duplicate vertices removed.")
    parser.add_argument("source_xml", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    report = normalize_consecutive_duplicate_vertices(args.source_xml, output_dir / "annotations.xml")
    (output_dir / "normalization_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
