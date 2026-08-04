# Steel billet visible-front-face baseline report

Date: 2026-08-01  
Status: `PROVISIONAL_BASELINE_COMPLETE`  
Target: `billet_front_face` visible pixels only

## Dataset and split

- Accepted CVAT snapshot: `cvat_task_2_2026-07-31_owner_accepted`
- Local annotated data: 65 images, 912 instances
- Train: 45 images / 628 instances / 15 scene groups
- Validation: 10 images / 148 instances / 2 scene groups
- Test: 10 images / 136 instances / 3 scene groups
- Scene overlap across splits: none
- Derived training export: `data/processed/yolo_seg_v3`
- All 65 derived images are independent copies. A terminal JPEG EOI marker was
  added only to derived files so Ultralytics would not re-encode the source
  images during scanning.

## Training

- Model: pretrained `yolo26n-seg.pt`
- Ultralytics: 8.4.114
- PyTorch: 2.7.1+cu118
- GPU: NVIDIA GeForce RTX 3050 Ti Laptop GPU, 4 GB
- Resolution: 896 px
- Batch size: 2
- Optimizer: AdamW, initial learning rate 0.001, cosine schedule
- Maximum epochs: 100
- Early stopping patience: 20
- Completed epochs: 74
- Recorded training time: 2179.09 seconds (about 36.3 minutes)
- Observed peak GPU allocation during training: about 2.8 GB

The selected `best.pt` checkpoint was chosen by Ultralytics' combined
validation fitness. Its final validation re-check produced:

| Metric | Validation |
|---|---:|
| Mask precision | 0.845 |
| Mask recall | 0.626 |
| Mask mAP50 | 0.768 |
| Mask mAP50-95 | 0.595 |

The highest mask-only mAP50-95 recorded in `results.csv` was 0.60267 at epoch
64. This is reported separately because it is not necessarily the checkpoint
selected by the framework's combined box-and-mask fitness.

## One-time frozen test assessment

The baseline configuration was frozen before opening the test split. The test
was evaluated once and is not available for hyperparameter selection.

| Metric | Test |
|---|---:|
| Images / instances | 10 / 136 |
| Mask precision | 0.8504 |
| Mask recall | 0.7939 |
| Mask mAP50 | 0.9062 |
| Mask mAP50-95 | 0.7483 |
| Inference time | 49.8 ms/image |

The test score is materially higher than validation. Visual inspection shows
that the test subset contains easier, larger and less crowded faces, while the
validation subset contains dense stacks with smaller, shadowed and partially
occluded faces. Therefore the test result must not be generalized to all
factory conditions or treated as production readiness.

## Visual error observations

- Large, isolated and close-range faces are usually segmented well.
- Dense validation stacks still contain missed small/distant faces.
- Strong occlusion, deep shadow and low apparent face area reduce recall.
- Several correct detections in crowded scenes have low confidence, indicating
  limited training diversity rather than a stable operating threshold.
- These masks validate only the segmentation stage. They do not establish
  four-corner geometry, camera calibration or physical rhombicity accuracy.

## Data integrity incident and recovery

The first aborted smoke test used a derived export containing hardlinks.
Ultralytics attempted to repair JPEG endings and modified 55 linked source
files. Training was stopped before an epoch completed. Exact originals were
recovered from the read-only CVAT task-2 volume after matching all 55 expected
SHA-256 hashes. Modified versions were retained under
`outputs/recovery_20260801/modified_backups` for traceability. All hardlinks
were broken, the invalid export was quarantined, and the final audit confirms:

- source inventory mismatches: 0 / 662;
- final derived-image hash mismatches: 0 / 65;
- test suite: 11 passed.

## Decision and next gate

This annotation volume is sufficient for a useful first baseline and for
model-assisted active learning. It is not sufficient for production acceptance.
The next annotation round should not be random. Run the frozen baseline over
the unlabeled pool and select approximately 40-80 diverse, difficult frames
that emphasize crowded stacks, small/distant faces, heavy occlusion, deep
shadow, truncation and unusual camera viewpoints. Keep the current test split
frozen. Retrain and compare on validation before any geometry or rhombicity
work begins.

## Traceability

- Best checkpoint SHA-256: `92df69b295851ec9967816dc8ddc599a63fd6696bacf10da9f71c42e68bd892b`
- Training config SHA-256: `607003ec969dc1b79617fa659388987884f7854d28c27921ff2f88e1b4193e8e`
- Dataset conversion summary SHA-256: `ba1f1b15a87f32f6ebeef5a9215924c45ebc02f8ed7deee3ab80b7ffbfb7582e`
- Test evaluation config explicitly states `use_results_for_hyperparameter_tuning: false`.
