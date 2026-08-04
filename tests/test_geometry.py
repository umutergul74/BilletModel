from steel_billet_vision.qa.geometry import area, has_duplicate_vertices, has_out_of_bounds_vertex, is_concave, is_self_intersecting


def test_area_and_concavity() -> None:
    square = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    concave = [(0.0, 0.0), (2.0, 0.0), (1.0, 1.0), (2.0, 2.0), (0.0, 2.0)]
    assert area(square) == 4.0
    assert not is_concave(square)
    assert is_concave(concave)


def test_self_intersection_and_duplicate_vertices() -> None:
    bow_tie = [(0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0)]
    repeated = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (2.0, 2.0)]
    assert is_self_intersecting(bow_tie)
    assert has_duplicate_vertices(repeated)


def test_cvat_border_coordinate_convention() -> None:
    border = [(0.0, 0.0), (3000.0, 0.0), (3000.0, 4000.0)]
    beyond = [(0.0, 0.0), (3000.1, 0.0), (10.0, 10.0)]
    assert not has_out_of_bounds_vertex(border, 3000, 4000)
    assert has_out_of_bounds_vertex(beyond, 3000, 4000)
