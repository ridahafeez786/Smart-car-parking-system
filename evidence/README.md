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

## Automatic parking verification (13 October 2026)

- 13 automated tests passed: minute billing, legacy migration, exact upload toggling, idempotent event retry, stable camera readings, hold suppression, blank rearming, uncertainty and restart persistence.
- Isolated dashboard with real YOLO11n and EasyOCR: Cars323.png uploaded twice, producing entry then exit after 24 seconds; receipt PKR 10. Screenshot: automatic_receipt_test.jpg.
- Real /parking/scan camera-frame requests using Cars307.png and blank frames: three stable reads entered, repeated plate suppressed, blank sequence rearmed, three stable reads exited; receipt PKR 10.
- Updated live-camera controls rendered at port 8000 with no browser console errors. Screenshot: automatic_dashboard_test.jpg.
- These are workflow checks, not an OCR accuracy benchmark. Physical webcam capture and the user's phone-screen demonstration still need testing.
- All test visits were stored in a separate temporary database on port 8001. The normal database was not populated by these tests.

## Stacked plate OCR fix (13 October 2026)

Cars320.png originally returned MA2662KAJ09 with a 0.735 average OCR score and was correctly rejected by the 0.80 automatic threshold. Allowing hyphens during OCR, resizing the crop toward 400 px width, beam decoding and spatial block ordering now return KA-09 MA 2662 / KA09MA2662. The minimum block score is 0.8403. Scores now use the weakest block rather than the average.

17 unit tests passed. Actual inference and automatic entry passed for Cars320, Cars307 and Cars323; Cars320 exit also passed, all against temporary storage. This is targeted regression verification, not held-out OCR accuracy evaluation. Dashboard rejection notices now explicitly state that no vehicle was added/removed and show the thresholds beside low-confidence detections.

## CPU OCR replacement (13 October 2026)

Installed RapidOCR 3.10.0 / ONNX Runtime 1.31.0, using bundled PP-OCRv6 small detection and recognition models. Added wide-crop recognition fallback requiring agreement across original and inverted grayscale inputs. Made this pipeline the default; EasyOCR remains selectable through SMARTPARK_OCR.

Four development examples: EasyOCR exact matches 3/4; RapidOCR pipeline 4/4. See ocr_comparison.json and scripts/compare_ocr.py. These already-inspected examples informed the change and are not a held-out OCR benchmark. Thresholds remain 0.50 detection / 0.80 OCR. Scores are not accuracy probabilities.

21 unit tests passed. A read-only call to the running /predict endpoint returned Cars281 as MH01DB0001 with score 0.9705 and engine rapidocr. No parking records were changed by this comparison or that API check.
