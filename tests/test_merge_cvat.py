from pathlib import Path

from steel_billet_vision.annotation.merge_cvat import merge_cvat_image_exports


def _write_export(path: Path, image_name: str) -> None:
    path.write_text(
        f"""<annotations><version>1.1</version><meta><job><id>1</id></job></meta><image id="0" name="{image_name}" width="10" height="10"><polygon label="billet_front_face" source="manual" occluded="0" points="0,0;9,0;9,9" z_order="0" /></image></annotations>""",
        encoding="utf-8",
    )


def test_merge_reconciles_images_and_instances(tmp_path: Path) -> None:
    left = tmp_path / "left.xml"
    right = tmp_path / "right.xml"
    _write_export(left, "a.jpg")
    _write_export(right, "b.jpg")

    report = merge_cvat_image_exports([left, right], tmp_path / "merged" / "annotations.xml", "merged")

    assert report["images"] == 2
    assert report["instances"] == 2
