from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
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


def merge_cvat_image_exports(source_xmls: Iterable[Path], output_xml: Path, dataset_name: str) -> dict[str, object]:
    sources = [path.resolve() for path in source_xmls]
    output_xml = output_xml.resolve()
    if output_xml.exists():
        raise FileExistsError(f"Refusing to overwrite merged annotation XML: {output_xml}")
    if len(sources) < 2:
        raise ValueError("At least two CVAT XML sources are required")

    images_by_name: dict[str, ET.Element] = {}
    source_records: list[dict[str, object]] = []
    label_names: set[str] = set()
    for source in sources:
        export = load_cvat_images_xml(source)
        tree_root = ET.parse(source).getroot()
        source_instances = 0
        for image_node in tree_root.findall("image"):
            name = image_node.attrib["name"]
            if name in images_by_name:
                raise ValueError(f"Duplicate image name across CVAT sources: {name}")
            images_by_name[name] = deepcopy(image_node)
            polygons = image_node.findall("polygon")
            source_instances += len(polygons)
            label_names.update(node.attrib.get("label", "") for node in polygons)
        source_records.append(
            {
                "path": str(source),
                "sha256": _sha256(source),
                "images": len(export.images),
                "instances": source_instances,
            }
        )
    if label_names != {"billet_front_face"}:
        raise ValueError(f"Unexpected merged label schema: {sorted(label_names)}")

    root = ET.Element("annotations")
    ET.SubElement(root, "version").text = "1.1"
    meta = ET.SubElement(root, "meta")
    task = ET.SubElement(meta, "task")
    ET.SubElement(task, "name").text = dataset_name
    ET.SubElement(task, "size").text = str(len(images_by_name))
    ET.SubElement(task, "mode").text = "annotation"
    labels = ET.SubElement(task, "labels")
    label = ET.SubElement(labels, "label")
    ET.SubElement(label, "name").text = "billet_front_face"
    ET.SubElement(label, "color").text = "#d2e9e9"
    ET.SubElement(label, "type").text = "polygon"
    ET.SubElement(meta, "dumped").text = datetime.now(timezone.utc).isoformat()

    for new_id, name in enumerate(sorted(images_by_name)):
        image_node = images_by_name[name]
        image_node.set("id", str(new_id))
        root.append(image_node)

    output_xml.parent.mkdir(parents=True, exist_ok=False)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_xml, encoding="utf-8", xml_declaration=True)
    merged = load_cvat_images_xml(output_xml)
    merged_instances = sum(len(image.polygons) for image in merged.images)
    expected_instances = sum(int(record["instances"]) for record in source_records)
    if len(merged.images) != len(images_by_name) or merged_instances != expected_instances:
        raise RuntimeError("Merged CVAT export failed count reconciliation")

    return {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_name": dataset_name,
        "sources": source_records,
        "output_xml": str(output_xml),
        "output_xml_sha256": _sha256(output_xml),
        "images": len(merged.images),
        "instances": merged_instances,
        "labels": sorted(label_names),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge non-overlapping CVAT for Images XML exports.")
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-name", required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    report = merge_cvat_image_exports(args.source, output_dir / "annotations.xml", args.dataset_name)
    (output_dir / "merge_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
