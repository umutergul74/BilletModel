# Annotation audit report — CVAT job 2

Status: **REVIEW_REQUIRED / UNVERIFIED**  
Audit scope: Phase 0–4 only  
Annotation version: `cvat_job_2_dump_2026-07-30T08-47-31Z_unverified`

## Source and format

- Format: CVAT for Images 1.1 XML.
- CVAT job: 2, frames 0–74, polygon annotations.
- Class schema: one class, `billet_front_face`.
- Source: manual polygons; no instance attributes were present.
- Original export and immutable snapshot SHA-256: `DC7C774FD1C778A8105FD211A16927703E2A6BC7741FD3F3C1CA11F50EB40CB4`.
- The XML and ZIP are preserved under `data/annotations/unverified/cvat_job_2_2026-07-30/`.

## Measured annotation inventory

| Item | Count |
|---|---:|
| CVAT job frames | 75 |
| Annotated frames | 68 |
| Empty frames | 7 |
| Total polygon instances | 915 |
| Source frames present | 69 |
| Source frames missing | 6 |
| Annotated source frames available for visual review | 63 |

Vertex distribution: 8 triangles, 751 four-vertex polygons, 104 five-vertex, 48 six-vertex, 2 seven-vertex, 1 eight-vertex, and 1 nine-vertex polygon. This is a topology description, not a correctness score.

## Automated review signals

| Signal | Instances | Interpretation |
|---|---:|---|
| `UNVERIFIED_HUMAN_ANNOTATION` | 915 | Every instance needs a human quality decision. |
| `MISSING_SOURCE_IMAGE` | 61 | Visual review is blocked for these instances. |
| `MULTISIDED_VISIBLE_REGION_REVIEW` | 156 | Potentially valid occlusion/truncation topology; inspect physically. |
| `CONCAVE_VISIBLE_REGION_REVIEW` | 80 | Potentially valid visible region; do not convexify automatically. |
| `FRAME_BOUNDARY_TRUNCATION_REVIEW` | 77 | Confirm the mask stops at the frame and contains no invented area. |
| `SELF_INTERSECTION` | 13 | Structural error candidate; inspect vertex ordering in CVAT. |
| `DUPLICATE_VERTEX` | 11 | Structural cleanup candidate; do not change boundary meaning. |
| `TRIANGULAR_VISIBLE_REGION_REVIEW` | 8 | Triangle may be correct if genuine occlusion leaves only that region. |
| `VERY_SMALL_MASK_REVIEW` | 2 | Decide valid extreme occlusion versus accidental fragment/ambiguity. |

No likely duplicate polygons or substantial polygon overlaps exceeded the configured raster thresholds. This does not prove that the image has no duplicate physical instances or missing billets.

Review priority totals are P0=61 (missing source), P1=15 (structural/small-mask candidates), P2=172 (topology/truncation interpretation), and P3=667 (otherwise unverified). Priorities are workflow ordering, not quality labels.

## Exact P0 missing-source frames

| Image ID | Filename | Polygon count |
|---:|---|---:|
| 37 | `20260729_100242.jpg` | 1 |
| 38 | `20260729_102145.jpg` | 0 |
| 47 | `20260729_102325.jpg` | 4 |
| 56 | `20260729_102810(0).jpg` | 1 |
| 59 | `20260729_102848.jpg` | 2 |
| 71 | `20260729_103914(0).jpg` | 53 |

Restore the exact files before deciding these annotations. Filename-only substitutions are insufficient; dimensions and scene identity must match the CVAT export.

## Exact structural/small-mask candidates

| Image ID | Filename | Instance | Signals |
|---:|---|---:|---|
| 0 | `20260729_092432(0).jpg` | 22 | duplicate vertex, self-intersection |
| 5 | `20260729_092444.jpg` | 3 | duplicate vertex, self-intersection |
| 6 | `20260729_092446(0).jpg` | 16 | duplicate vertex, self-intersection |
| 6 | `20260729_092446(0).jpg` | 17 | very small, triangle |
| 6 | `20260729_092446(0).jpg` | 18 | very small, multi-sided |
| 8 | `20260729_092449.jpg` | 4 | self-intersection |
| 14 | `20260729_095136(0).jpg` | 20 | self-intersection |
| 20 | `20260729_095330(0).jpg` | 2 | duplicate vertex, self-intersection |
| 22 | `20260729_095341.jpg` | 5 | duplicate vertex, self-intersection |
| 22 | `20260729_095341.jpg` | 7 | duplicate vertex, self-intersection |
| 22 | `20260729_095341.jpg` | 10 | duplicate vertex, self-intersection |
| 27 | `20260729_095410(0).jpg` | 3 | duplicate vertex, self-intersection |
| 27 | `20260729_095410(0).jpg` | 6 | duplicate vertex, self-intersection |
| 28 | `20260729_095512(0).jpg` | 21 | duplicate vertex, self-intersection |
| 66 | `20260729_103816.jpg` | 10 | duplicate vertex, self-intersection |

## Triangle review queue

These eight instances are review signals, not presumed errors: image 2 instance 8; image 3 instance 6; image 5 instance 7; image 6 instances 1, 13, and 17; image 7 instances 9 and 14. Confirm that each triangle is the genuinely visible portion rather than an accidental incomplete polygon.

## Visual contact-sheet screening

The 69 available overlays were visually screened at contact-sheet level. This screening is deliberately non-exhaustive and does not replace instance-by-instance approval.

- Every available zero-polygon frame (IDs 55, 67, 68, 69, 70, and 74) visibly contains billet front-face candidates. These are likely missing-annotation cases and require image-level correction review.
- Dense frames 62–66 and 72–73 visibly contain unmasked front-face candidates alongside annotated faces. Treat these as likely incomplete images and reconcile all visible instances in CVAT.
- Many existing masks visually align with front faces, but contact-sheet resolution is insufficient to approve side-face exclusion, shadow boundaries, hidden completion, or sub-pixel boundary precision.

## What automation cannot decide

`NOT_YET_MEASURED` by automation: side-face inclusion, hidden-geometry completion, shadow-versus-occlusion interpretation, whether every visible billet is annotated, and whether boundaries are precise enough for future contour learning. Those decisions are explicitly presented to the human reviewer.

## Mandatory stop

Do not train, promote this export to ground truth, audit/split the full dataset as a finalized dataset, or compute geometry/rhombicity. Complete the human review, correct in CVAT, export a new version, and rerun structural validation first.

