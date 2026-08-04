# Owner Acceptance Record

- Decision date: 2026-08-03 (Europe/Istanbul)
- Dataset: active learning round 01, 34 images
- CVAT source export: `active_learning_round_01_cvat_export_v2.zip`
- Source export SHA-256: `B5315165F0B24299FDC36185324CBD18D9935DCFDD4C9EF8C7A04840279C1032`
- Human authority: dataset owner (`umutergul` in CVAT metadata)
- Decision: `OWNER_ACCEPTED`

The owner explicitly accepted remaining boundary ambiguity caused by shadow, perspective, and indistinct physical edges and instructed the pipeline to continue without another manual correction round.

The accepted `annotations.xml` is derived from the immutable V2 export. The only automated edits were removal of two exact consecutive duplicate vertices; image count, instance count, and polygon geometry were otherwise preserved. See `normalization_report.json`.
