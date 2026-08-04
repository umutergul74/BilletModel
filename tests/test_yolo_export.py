from steel_billet_vision.data.yolo_export import _copy_image, _ensure_terminal_jpeg_eoi, _format_polygon


def test_polygon_normalization_and_clipping() -> None:
    line = _format_polygon(((-1.0, 0.0), (50.0, 25.0), (101.0, 50.0)), 100, 50)
    assert line == "0 0.00000000 0.00000000 0.50000000 0.50000000 1.00000000 1.00000000"


def test_image_export_is_an_independent_copy(tmp_path) -> None:
    source = tmp_path / "source.jpg"
    destination = tmp_path / "derived.jpg"
    source.write_bytes(b"immutable-source")

    assert _copy_image(source, destination) == "independent_copy"
    destination.write_bytes(b"changed-derived-copy")

    assert source.read_bytes() == b"immutable-source"


def test_jpeg_terminal_eoi_is_appended_only_when_needed(tmp_path) -> None:
    image = tmp_path / "image.jpg"
    image.write_bytes(b"jpeg-payload")

    assert _ensure_terminal_jpeg_eoi(image) == "terminal_eoi_appended"
    assert image.read_bytes() == b"jpeg-payload\xff\xd9"
    assert _ensure_terminal_jpeg_eoi(image) == "already_terminal_eoi"
    assert image.read_bytes() == b"jpeg-payload\xff\xd9"
