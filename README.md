# Steel Billet Visible-Front-Face QA

The dataset owner accepted the updated manual annotation export as the current baseline ground truth on 2026-07-31. The active snapshot contains 70 annotated images and 976 `billet_front_face` polygons. The former per-instance QA interface is retained only as an inactive historical diagnostic.

## Measured Phase 0–4 state

- 662 JPEG source images are present at the workspace root.
- CVAT for Images 1.1 export: job 2, frames 0–74.
- 75 job frames, 68 annotated frames, 7 empty frames, 915 manual polygons.
- Label schema: one polygon class, `billet_front_face`.
- Six CVAT-referenced source files are absent from the workspace.
- All 976 existing polygons across 70 exported frames are owner-accepted.
- Five zero-polygon frames were intentionally removed from the CVAT task; the remaining exported frames are all annotated.
- Five exported/annotated images are absent locally and are excluded from training manifests unless restored.

See [the audit report](outputs/annotation_qa/ANNOTATION_AUDIT_REPORT.md) and [the review guide](outputs/annotation_qa/REVIEW_GUIDE.md).

## Run the reproducible QA pipeline

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
python scripts\run_annotation_qa.py --config configs\annotation_qa.yaml
python scripts\build_contact_sheets.py
python -m http.server 8765
```

Then open `http://localhost:8765/outputs/annotation_qa/review.html`. The page supports filename/signal filtering, per-instance quality decisions, notes, browser-local autosave, and JSON decision export.

## Active workflow

Use `configs/dataset.yaml` as the active dataset/annotation configuration. Existing manual masks are not subject to the retired per-instance review process. Missing local images must not enter training until their exact source files are restored.
