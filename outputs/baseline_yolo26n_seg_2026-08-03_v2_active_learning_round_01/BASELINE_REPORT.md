# Active-Learning Baseline V2 Report

## Decision

Status: `PROVISIONAL_ACTIVE_LEARNING_BASELINE`

The dataset owner accepted the remaining shadow and boundary ambiguity in active-learning round 01. No polygon was forced to four vertices and no hidden face region was completed. Two exact consecutive duplicate vertices were removed without changing the image or instance count.

This checkpoint is accepted as the next segmentation baseline. It is not approved for physical geometry, rhombicity, or production quality decisions.

## Data lineage

- Accepted merged CVAT export: `data/annotations/accepted/seed_plus_active_learning_round_01_2026-08-03/annotations.xml`
- Trainable dataset: 99 images, 1,453 visible-front-face masks
- Train split: 79 images, 1,169 masks
- Validation split: 10 images, 148 masks
- Frozen test split: 10 images, 136 masks
- New active-learning contribution: 34 images, 541 masks, all assigned to train
- Split policy: prior validation/test scene groups preserved; no scene group leakage; source hash audit passed
- Five previously annotated images missing from the local source collection remained excluded

## Training

- Parent checkpoint: `baseline_yolo26n_seg_2026-08-01_v1/weights/best.pt`
- Model: YOLO26n-seg
- Resolution: 896 px
- Batch: 2
- Optimizer: AdamW
- Maximum epochs: 80
- Patience: 20
- Completed epochs: 70 (early stopping)
- Seed: 20260731, deterministic mode enabled
- Runtime: Python 3.13.7, PyTorch 2.7.1+cu118, Ultralytics 8.4.114
- GPU: NVIDIA GeForce RTX 3050 Ti Laptop GPU, 4 GB

## Selected checkpoint

- Path: `experiments/baseline_yolo26n_seg_2026-08-03_v2_active_learning_round_01/weights/best.pt`
- SHA-256: `7fa7ba39de4f801acb8271eb4caddd3b5fb042d174b9598c3bdf575c57d8da58`

## Independent validation audit

The selected checkpoint was re-evaluated on the unchanged validation split after training.

| Metric | Result |
|---|---:|
| Mask precision | 0.824845 |
| Mask recall | 0.790541 |
| Mask mAP50 | 0.863746 |
| Mask mAP50-95 | 0.687292 |
| Box precision | 0.817795 |
| Box recall | 0.783784 |
| Box mAP50 | 0.850305 |
| Box mAP50-95 | 0.723939 |
| Inference time | 73.09 ms/image |

Compared with the rounded V1 validation result, mask mAP50-95 increased from 0.595 to 0.687 and recall increased from 0.626 to 0.791. The validation set is small, so these values are evidence of improvement rather than a production guarantee.

## Qualitative error review

The validation prediction sheets show reliable coverage of many clear, medium, and large billet front faces, including dark or shadowed faces. Remaining errors concentrate in:

- very small and distant faces;
- heavily overlapping or tightly touching faces;
- the darkest and lowest-contrast boundaries;
- partially visible faces where confidence falls to roughly 0.3-0.5.

These cases should drive the next active-learning selection. They should not be corrected by inventing hidden pixels or forcing a quadrilateral.

## Holdout policy and next gate

The frozen test split was not used during this V2 training or checkpoint selection. The next recommended step is structured inference over the unlabeled image pool, followed by scene-diverse selection of the highest-value failure cases for a second annotation round. Geometry eligibility, four-corner reconstruction, calibration, and rhombicity remain separate later gates.
