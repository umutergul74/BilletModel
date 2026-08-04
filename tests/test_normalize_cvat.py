from pathlib import Path

from steel_billet_vision.annotation.cvat import load_cvat_images_xml
from steel_billet_vision.annotation.normalize_cvat import normalize_consecutive_duplicate_vertices


def test_normalizer_removes_only_consecutive_duplicate_vertices(tmp_path: Path) -> None:
    source = tmp_path / "source.xml"
    source.write_text(
        """<annotations><version>1.1</version><meta><job><id>1</id></job></meta><image id="0" name="x.jpg" width="10" height="10"><polygon label="billet_front_face" source="manual" occluded="0" points="0,0;9,0;9,9;9,9;0,9" z_order="0" /></image></annotations>""",
        encoding="utf-8",
    )
    output = tmp_path / "accepted" / "annotations.xml"

    report = normalize_consecutive_duplicate_vertices(source, output)
    export = load_cvat_images_xml(output)

    assert report["removed_vertex_count"] == 1
    assert export.images[0].polygons[0].points == ((0.0, 0.0), (9.0, 0.0), (9.0, 9.0), (0.0, 9.0))
