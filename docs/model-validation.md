# Pothole model replacement — 2026-10-13

## Reproduced problem

The initial `keremberke/yolov8s-pothole-segmentation` checkpoint detected the included dataset sample but missed both additional photos in the local examples folder. At 5% confidence it emitted poorly localized boxes; reducing the threshold was not an adequate fix.

## Replacement

Default: [Harisanth/Pothole-Finetuned-YOLOv8](https://huggingface.co/Harisanth/Pothole-Finetuned-YOLOv8), pinned at `30a4d21de50998dbfa7cc79abb0d7a0d4aa71a4d` and checksum-verified by the download script. The checkpoint exposes the `pothole` class. The upstream card does not provide a reproducible dataset split; its performance claims are not treated as independently verified.

Both models were compared using CPU inference, RGB PIL input, 640-pixel letterboxing, **confidence 0.35**, and NMS IoU 0.5. The confidence threshold has not been reduced.

| Image | Original checkpoint | Replacement checkpoint |
| --- | --- | --- |
| Water-filled pothole (`pothole img.jpg`) | No detection | Correctly localized, 90.4% confidence |
| Broken-asphalt pothole (`potholeimg.webp`) | No detection | Correctly localized, 87.1% confidence |
| Attributed sample (`pothole.jpg`) | Main pothole at 74.7% | Main pothole at 90.2%; additional candidate regions also detected |
| Ultralytics `bus.jpg` negative control | Two false detections | No detections |
| Ultralytics `zidane.jpg` negative control | No detections | No detections |

The two user-image bounding boxes were visually inspected. The real-model tests require at least 0.5 IoU against approximate manually reviewed bounds, so a box elsewhere in the frame cannot pass. Uniform black, gray, and white frames are also negative controls.

Other locally evaluated candidates included `peterhdd/pothole-detection-yolov8` (missed the original sample and poorly localized the broken-asphalt photo) and `Samdutse/pothole-yolov8` (localized the three main potholes). The replacement was selected for the reported failures, not on a representative held-out benchmark.

## Limits

These are a small regression set used during model selection, **not** an independent accuracy evaluation. Confidence scores are not measured correctness probabilities. Unknown overlap with upstream training data is possible. Additional candidate regions on the original image have not all been labeled, so this check does not establish overall precision or recall. Validate on diverse independently labeled roads, lighting, camera positions, and negative examples before relying on the system operationally.

The two local user photos have not been copied into a new distributable test dataset. Their tests skip when the files are absent. Original sample attribution remains in `examples/ATTRIBUTION.md`.
