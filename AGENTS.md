# AGENTS.md — Steel Billet Vision & Rhombicity Project

## Mission
Build a production-grade computer-vision system for real industrial steel billets. The first objective is reliable instance segmentation of each billet's **visible front face**. Later stages may estimate underlying front-face geometry, calibrate the camera, and quantify rhombicity/diamondness.

The system is intended for an actual factory environment. Optimize for correctness, traceability, robustness, maintainability, safe failure, and measurable engineering performance—not for a demo.

## Non-negotiable principles

1. **Inspect before changing.** First inspect the repository, ~700 real images, existing ~50 CVAT annotations, annotation format, hardware assumptions, and current tooling.
2. **Existing annotations are unverified.** Never treat the ~50 pre-existing CVAT images as ground truth until audited and human-verified.
3. **Visible face is the segmentation target.** Annotate only the portion of the billet front face that is actually visible.
4. **Polygon topology is not fixed.** A valid visible mask can be triangular, quadrilateral, pentagonal, hexagonal, or concave because of occlusion, truncation, or perspective. Do not force four vertices.
5. **Never hallucinate hidden pixels.** Do not extend a segmentation mask through an occluding billet or beyond the image frame.
6. **Separate the problems.** Detection/segmentation, geometry reconstruction, calibration, and rhombicity are separate stages with separate confidence/eligibility decisions.
7. **Shadow is not occlusion.** A physically visible but dark face remains part of the mask; a face hidden by another object is not annotated.
8. **Uncertainty is a valid output.** If geometry is insufficient, return an explicit non-measurable state instead of inventing a value.
9. **No metric fabrication.** Never invent dataset statistics, model scores, calibration values, physical dimensions, or rhombicity measurements.
10. **No leakage.** Split by scene/capture sequence/near-duplicate group where appropriate, not merely by random filename.
11. **Calibration before metric claims.** The nominal 150 mm × 150 mm cross-section is domain knowledge, not a pixel-to-mm scale.
12. **Human review gates are mandatory.** If annotation quality or geometry cannot be trusted, stop at the review gate and report exactly what must be reviewed.

## Dataset context

The dataset contains approximately 700 real factory photographs. Most images contain roughly 15–20 billets in crowded stacks. Common conditions include overlap, touching, diagonal orientations, different depths, partial occlusion, shadows, reflections, uneven illumination, partial frame truncation, labels/QR codes, and scale variation. Some single-billet close-ups exist and are useful for boundary/geometry learning.

## Required development order

1. Inspect repository and environment.
2. Locate and parse CVAT annotations.
3. Audit the existing ~50 annotations.
4. Build/verify visual QA tooling.
5. Produce a human review list.
6. Stop for human verification when required.
7. Audit all images for quality, duplicates, near-duplicates, scene/capture groups, and diversity.
8. Design leakage-safe train/validation/test splits.
9. Establish a verified seed dataset.
10. Train a baseline instance-segmentation model.
11. Evaluate and perform structured error analysis.
12. Use model-assisted annotation / active learning.
13. Stabilize segmentation.
14. Add visibility/occlusion and geometry eligibility.
15. Add contour/edge/corner estimation.
16. Calibrate camera and validate metric geometry.
17. Develop experimental rhombicity metrics.
18. Validate against factory engineering criteria and real production conditions.
19. Only then design production deployment.

## Annotation contract

The annotation target is `billet_front_face`.

Correct:
- visible front-face pixels;
- shadowed but physically visible front-face pixels;
- visible partial regions;
- irregular, multi-sided, or concave visible regions when physically justified.

Incorrect:
- hidden portions behind another billet;
- side/top/bottom surfaces;
- background;
- shadows as separate objects;
- invented corners;
- completion outside the image.

A triangular mask is not inherently wrong. A six-sided mask is not inherently wrong. Shape complexity is a review signal, not an error criterion.

## Geometry contract

Segmentation answers: "Which front-face pixels are visible?"

Geometry answers: "Can the underlying four-sided front-face geometry be reliably inferred?"

Rhombicity answers: "How much does validated physical geometry deviate from the nominal square?"

Do not derive four corners by simply taking polygon vertices. Do not force a four-corner model when evidence is insufficient.

## Industrial safety contract

A wrong confident measurement is worse than a rejected measurement.

Use explicit states such as:
- `DETECTED`
- `VISIBLE`
- `PARTIALLY_VISIBLE`
- `OCCLUDED`
- `GEOMETRY_ELIGIBLE`
- `INSUFFICIENT_FOR_GEOMETRY`
- `OUT_OF_FRAME`
- `AMBIGUOUS`
- `REVIEW_REQUIRED`
- `MEASUREMENT_VALID`

Never silently convert uncertainty into a numeric quality decision.

## Engineering standards

Prefer:
- modular components;
- typed/config-driven interfaces;
- deterministic pipelines;
- unit/integration tests;
- versioned datasets and annotations;
- reproducible experiments;
- structured logs;
- clear schemas;
- explicit error handling;
- small composable scripts;
- documented assumptions;
- hardware-aware inference design.

Avoid:
- giant monolithic scripts;
- hidden global state;
- hard-coded machine-specific paths;
- destructive dataset edits;
- silent annotation rewriting;
- untracked manual corrections;
- unexplained thresholds;
- metric claims without evidence.

## Completion criteria

A task is not complete merely because code runs. It is complete when:
- assumptions are documented;
- tests pass;
- outputs are inspectable;
- failure cases are handled;
- data lineage is preserved;
- evaluation is reproducible;
- the implementation matches the project's annotation and geometry contracts;
- any required human review has actually occurred.

Read the relevant skill under `.agents/skills/` before performing work in that area.
