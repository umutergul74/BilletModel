from __future__ import annotations

from collections.abc import Sequence
import math

Point = tuple[float, float]


def signed_area(points: Sequence[Point]) -> float:
    if len(points) < 3:
        return 0.0
    return 0.5 * sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
    )


def area(points: Sequence[Point]) -> float:
    return abs(signed_area(points))


def orientation(a: Point, b: Point, c: Point, eps: float = 1e-9) -> int:
    value = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if abs(value) <= eps:
        return 0
    return 1 if value > 0 else -1


def _on_segment(a: Point, b: Point, p: Point, eps: float = 1e-9) -> bool:
    return (
        min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps
        and orientation(a, b, p, eps) == 0
    )


def segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    o1, o2 = orientation(a, b, c), orientation(a, b, d)
    o3, o4 = orientation(c, d, a), orientation(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    return any(
        (
            o1 == 0 and _on_segment(a, b, c),
            o2 == 0 and _on_segment(a, b, d),
            o3 == 0 and _on_segment(c, d, a),
            o4 == 0 and _on_segment(c, d, b),
        )
    )


def is_self_intersecting(points: Sequence[Point]) -> bool:
    n = len(points)
    if n < 4:
        return False
    edges = [(points[i], points[(i + 1) % n]) for i in range(n)]
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if j <= i:
                continue
            if j in {i, (i + 1) % n} or i in {j, (j + 1) % n}:
                continue
            if i == 0 and j == n - 1:
                continue
            if segments_intersect(a, b, c, d):
                return True
    return False


def is_concave(points: Sequence[Point]) -> bool:
    if len(points) < 4:
        return False
    signs = {
        orientation(points[i - 1], points[i], points[(i + 1) % len(points)])
        for i in range(len(points))
    }
    signs.discard(0)
    return len(signs) > 1


def has_duplicate_vertices(points: Sequence[Point], eps: float = 1e-6) -> bool:
    for i, point in enumerate(points):
        for prior in points[:i]:
            if math.dist(point, prior) <= eps:
                return True
    return False


def touches_frame(points: Sequence[Point], width: int, height: int, tolerance: float) -> bool:
    return any(
        x <= tolerance or y <= tolerance or x >= width - 1 - tolerance or y >= height - 1 - tolerance
        for x, y in points
    )


def has_out_of_bounds_vertex(points: Sequence[Point], width: int, height: int, tolerance: float = 1e-6) -> bool:
    # CVAT image coordinates may legitimately land exactly on width/height at
    # the outer border. Values beyond those limits remain structurally invalid.
    return any(x < -tolerance or y < -tolerance or x > width + tolerance or y > height + tolerance for x, y in points)
