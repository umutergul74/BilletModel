# Human review guide

## Open the reviewer

From the workspace root:

```powershell
python -m http.server 8765
```

Open `http://localhost:8765/outputs/annotation_qa/review.html`.

The image is shown with colored masks, polygon outlines, vertices, and stable instance IDs. Filter by filename or signal such as `SELF_INTERSECTION`, `TRIANGULAR_VISIBLE_REGION_REVIEW`, `CONCAVE_VISIBLE_REGION_REVIEW`, or `FRAME_BOUNDARY_TRUNCATION_REVIEW`. Decisions are autosaved in this browser and can be exported as `review_decisions.json`.

## Decision for every instance

Assign exactly one human category:

- `GOOD`: physically correct visible front-face mask with adequate boundary precision.
- `MINOR_CORRECTION`: small boundary/vertex adjustment; physical instance and target are correct.
- `MAJOR_CORRECTION`: substantial redraw, hidden completion, side-face/background inclusion, or incorrect occlusion handling.
- `INVALID`: not a billet front face, duplicate physical instance, or unusable annotation.
- `AMBIGUOUS`: pixels cannot be reliably interpreted from the image.
- `REVIEW_REQUIRED`: defer because evidence or responsible reviewer is unavailable.

Visibility and quality are separate. A triangular, concave, multi-sided, or frame-truncated visible region can be `GOOD`.

## Required physical checks

For each instance, confirm that it:

1. corresponds to one real billet and the correct physical instance;
2. covers only physically visible front-face pixels;
3. excludes side/top/bottom surfaces, background, and other objects;
4. stops at occluding billets and does not invent a hidden fourth corner;
5. includes shadowed front-face pixels when the surface remains physically visible;
6. stops at the image border for truncated billets;
7. has a valid, non-self-intersecting polygon with sufficient boundary precision.

At image level, reconcile missing and duplicate instances. Zero-polygon frames must be explicitly confirmed rather than assumed complete.

## Correct in CVAT

1. Open CVAT job 2 and navigate to the frame by filename/image ID.
2. Select the matching polygon using the overlay's instance order and visible location.
3. For duplicate/crossing vertices, edit only the offending points; preserve the real visible boundary.
4. For occlusion errors, stop the rear billet polygon at the actual occluder. Never draw through the front billet.
5. For side-face inclusion, move the boundary to the physical front/side edge.
6. For missing instances, add one `billet_front_face` polygon per identifiable visible front face.
7. Do not force four vertices and do not complete hidden geometry.
8. Save in CVAT, then export **a new versioned snapshot**. Do not overwrite the original ZIP/XML.

After correction, place the new export under a new version directory, retain the exported decisions JSON, rerun the QA pipeline against that version, and reconcile frame/instance counts before marking it verified.

