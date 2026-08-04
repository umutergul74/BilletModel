from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


Point = tuple[float, float]


@dataclass(frozen=True)
class CvatPolygon:
    instance_index: int
    label: str
    points: tuple[Point, ...]
    source: str
    occluded: bool
    z_order: int
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CvatImage:
    image_id: int
    name: str
    width: int
    height: int
    polygons: tuple[CvatPolygon, ...]


@dataclass(frozen=True)
class CvatExport:
    format_version: str
    metadata: dict[str, Any]
    labels: tuple[dict[str, str], ...]
    images: tuple[CvatImage, ...]


def _text(parent: ET.Element | None, path: str, default: str = "") -> str:
    if parent is None:
        return default
    node = parent.find(path)
    return node.text.strip() if node is not None and node.text else default


def parse_points(raw: str) -> tuple[Point, ...]:
    points: list[Point] = []
    for item in raw.split(";"):
        x_raw, y_raw = item.split(",", maxsplit=1)
        points.append((float(x_raw), float(y_raw)))
    return tuple(points)


def load_cvat_images_xml(path: str | Path) -> CvatExport:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"CVAT annotation XML not found: {path}")
    root = ET.parse(path).getroot()
    if root.tag != "annotations":
        raise ValueError(f"Expected <annotations> root, found <{root.tag}>")

    meta = root.find("meta")
    job = meta.find("job") if meta is not None else None
    task = meta.find("task") if meta is not None else None
    scope = job if job is not None else task
    labels: list[dict[str, str]] = []
    if scope is not None:
        for label in scope.findall("./labels/label"):
            labels.append(
                {
                    "name": _text(label, "name"),
                    "type": _text(label, "type"),
                    "color": _text(label, "color"),
                }
            )

    images: list[CvatImage] = []
    for image_node in root.findall("image"):
        polygons: list[CvatPolygon] = []
        for instance_index, polygon_node in enumerate(image_node.findall("polygon"), start=1):
            attrs = {
                attr.attrib.get("name", ""): (attr.text or "")
                for attr in polygon_node.findall("attribute")
            }
            polygons.append(
                CvatPolygon(
                    instance_index=instance_index,
                    label=polygon_node.attrib.get("label", ""),
                    points=parse_points(polygon_node.attrib.get("points", "")),
                    source=polygon_node.attrib.get("source", ""),
                    occluded=polygon_node.attrib.get("occluded", "0") == "1",
                    z_order=int(polygon_node.attrib.get("z_order", "0")),
                    attributes=attrs,
                )
            )
        images.append(
            CvatImage(
                image_id=int(image_node.attrib["id"]),
                name=image_node.attrib["name"],
                width=int(image_node.attrib["width"]),
                height=int(image_node.attrib["height"]),
                polygons=tuple(polygons),
            )
        )

    metadata = {
        "job_id": _text(job, "id"),
        "task_id": _text(task, "id"),
        "task_name": _text(task, "name"),
        "job_size": _text(scope, "size"),
        "mode": _text(scope, "mode"),
        "start_frame": _text(scope, "start_frame"),
        "stop_frame": _text(scope, "stop_frame"),
        "created": _text(scope, "created"),
        "updated": _text(scope, "updated"),
        "dumped": _text(meta, "dumped"),
        "owner_username": _text(scope, "owner/username"),
    }
    return CvatExport(
        format_version=_text(root, "version"),
        metadata=metadata,
        labels=tuple(labels),
        images=tuple(images),
    )
