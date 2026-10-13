# Training evidence

The original PNG screenshots and screenshots containing test vehicle plates remain local and are excluded from Git. This repository includes these notes, the dataset audit, and `dashboard_ready.jpg` (the empty dashboard). Training and test results below were transcribed from the local evidence.

`dashboard_entry_test.jpg` and `dashboard_receipt_test.jpg` show a browser test of image upload, real detector/OCR output for `Cars323.png`, confirmed entry, checkout, and a PKR 100 receipt. These were captured using a temporary test database on port 8001; they do not represent real parking activity. History filtering and reopening the saved receipt were also verified through the UI.

`yolo_training_epochs_and_validation.png` records the YOLO11n Colab training run on a Tesla T4.

`api_plate_detection_success.png` records a successful request to the local FastAPI `/predict` endpoint: HTTP 200 and one license-plate detection for `Cars307.png`.

`api_two_plate_detections.png` records a successful request for `Cars311.png`: HTTP 200 and two detections. Both correspond to visible plates in the foreground and background vehicles; their confidence scores are 0.8145 and 0.5558.

`dataset_audit.txt` summarizes how the cleaned detection dataset was prepared.

`api_ocr_cars323.png` records HTTP 200 with OCR enabled for `Cars323.png`. The recognized text `TN99F2378` matches the original image's `TN 99 F 2378` after removing spaces. Detection confidence is 0.93 and OCR confidence is 0.9997. This is a visually checked example, not an aggregate accuracy measurement.

`api_ocr_cars307.png` records HTTP 200 with OCR enabled for `Cars307.png`. The recognized text `M906090K` matches the visible plate after removing separators. Detection confidence is 0.672; OCR confidence is 0.9921. The API returned `needs_manual_review: false` under its current confidence rule. This is one visually checked example, not a measurement of overall OCR accuracy.

- Training completed: 30/30 epochs in 0.173 hours (about 10.4 minutes).
- Best checkpoint: `best.pt` (5.5 MB), downloaded to the project root.
- Final validation split: 141 images and 157 plate instances.
- Validation metrics shown: precision 0.922, recall 0.866, mAP@50 0.914, mAP@50–95 0.634.
- Inference speed shown on the T4: 30.8 ms per validation image.

These are validation metrics from the training run, not the held-out test metrics. Report test-set results separately: 199 images, 274 plate instances, precision 0.938, recall 0.763, mAP@50 0.824, and mAP@50–95 0.575.
