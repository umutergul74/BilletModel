from pathlib import Path

from steel_billet_vision.annotation.cvat import load_cvat_images_xml


def test_load_minimal_cvat(tmp_path: Path) -> None:
    xml = tmp_path / "annotations.xml"
    xml.write_text("""<annotations><version>1.1</version><meta><job><id>2</id><labels><label><name>billet_front_face</name><type>polygon</type></label></labels></job></meta><image id="0" name="x.jpg" width="10" height="20"><polygon label="billet_front_face" source="manual" occluded="0" points="0,0;9,0;9,9" z_order="0" /></image></annotations>""", encoding="utf-8")
    export = load_cvat_images_xml(xml)
    assert export.format_version == "1.1"
    assert export.metadata["job_id"] == "2"
    assert export.images[0].polygons[0].points[-1] == (9.0, 9.0)


def test_load_task_level_cvat_export(tmp_path: Path) -> None:
    xml = tmp_path / "annotations.xml"
    xml.write_text(
        """<annotations><version>1.1</version><meta><task><id>4</id><name>round-1</name><size>1</size><labels><label><name>billet_front_face</name><type>any</type></label></labels></task></meta><image id="0" name="x.jpg" width="10" height="20"><polygon label="billet_front_face" source="manual" occluded="0" points="0,0;9,0;9,9" z_order="0" /></image></annotations>""",
        encoding="utf-8",
    )

    export = load_cvat_images_xml(xml)

    assert export.metadata["task_id"] == "4"
    assert export.metadata["task_name"] == "round-1"
    assert export.labels == ({"name": "billet_front_face", "type": "any", "color": ""},)
