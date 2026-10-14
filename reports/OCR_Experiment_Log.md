# Smart Parking System Final Report Draft

Author: Rida Hafeez  
Chapter prepared: 14 October 2026  
Status: OCR experimentation chapter for inclusion in the final capstone report. Other report chapters are not yet included here.

## OCR experimentation and improvement

### Objective and initial approach

We developed the recognition pipeline to identify a vehicle from a number-plate image and use that identity to open or close its parking session. We first combined our fine-tuned YOLO11n detector with pretrained English EasyOCR. YOLO located the plate, and EasyOCR read the characters from its cropped image. The detector's training labels contained bounding boxes rather than character transcriptions, so training YOLO did not train the OCR recognizer. Neither OCR engine was fine-tuned in these experiments.

EasyOCR provided a practical starting point because it integrated with Python and ran on the available CPU. Initial examples Cars307 and Cars323 produced the expected normalized identifiers M906090K and TN99F2378. However, these individual successes did not establish accuracy across other plate layouts, colours or image conditions.

### Failure analysis with EasyOCR

Two examples exposed different recognition problems. Cars320 contained the identifier KA-09 MA 2662, with a stacked prefix beside a larger numeric suffix. The initial output was MA2662KAJ09, with an average OCR score of approximately 0.735. The OCR output blocks were concatenated in the returned order rather than their spatial reading order. In addition, our original character allowlist excluded the hyphen, and the recognizer substituted another character for it.

Cars281 showed a green plate with white characters, MH 01 DB 0001. After the stacked-text improvements, EasyOCR still produced MH010B0001 with a score of 0.2686, confusing the letter D with the digit 0. Detection succeeded at approximately 0.805, but successful localization did not imply successful recognition.

The automatic workflow required detection confidence of at least 0.50 and OCR confidence of at least 0.80. Consequently, these uncertain reads did not create parking records. This behaviour was caused by recognition and acceptance rules rather than a failure to save records in SQLite. We retained the acceptance thresholds instead of lowering them to admit known incorrect identifiers.

### Preprocessing and text assembly experiments

We investigated crop size, image appearance and decoding before replacing the recognizer. Exploratory resizing to widths of 300, 600 and 900 pixels did not consistently correct the stacked prefix when hyphens were excluded. Larger crops alone therefore did not solve this example. We also tried grayscale and automatic contrast adjustment. These were development probes, not a controlled evaluation across the dataset.

The revised EasyOCR pipeline used a padded plate crop, resized toward 400 pixels in width with an enlargement limit of four times, Lanczos interpolation, an allowlist including hyphens, and beam-search decoding with beam width five. Spatial ordering assembled separate text blocks into rows or columns before normalization. Hyphens and other separators were then removed from the final identifier.

For Cars320, the revised pipeline returned KA-09 MA 2662 and normalized it to KA09MA2662. We also changed the reported OCR score from the mean of block scores to the minimum block score, so a poorly recognized prefix could not be hidden by a confidently recognized numeric suffix. The corrected EasyOCR result had a minimum block score of 0.8403. Because both preprocessing and score aggregation changed, this score should not be interpreted as a directly comparable increase from the original mean score.

Several changes were introduced together. We did not isolate each change in an ablation study, so we cannot attribute the entire improvement to one component. We added tests for stacked prefixes, ordinary two-line layouts, empty results and weak text fragments. Clearer dashboard messages explained when no vehicle was recorded and displayed the acceptance thresholds.

### Evaluation of a second OCR engine

We next installed RapidOCR 3.10.0 with ONNX Runtime 1.31.0 on the existing Windows Python environment. The installed package used PP-OCRv6 small detection and recognition models. Processing remained local on the CPU and did not require a GPU or a paid vision API. EasyOCR was retained as a selectable baseline.

Simply replacing EasyOCR with the default RapidOCR text-detection pipeline did not immediately solve Cars281: RapidOCR initially returned no text region for the green plate crop. This was a failure of text-region detection within an already localized plate. Feeding the whole YOLO crop directly to the recognizer produced MH 01 DB 0001. Recognition of an inverted grayscale version agreed with that reading.

We therefore added a conditional fallback. When the initial RapidOCR score is below 0.80 and the crop width-to-height ratio is at least 2.5, the recognizer processes the whole crop twice: once in its original appearance and once as inverted grayscale. The fallback is accepted only if the normalized strings agree and the lower of their scores reaches 0.80. We do not automatically substitute D, O or 0, and do not choose a result solely because it has the highest score. Agreement across two transformations is a consistency check, not independent proof of correctness. The aspect-ratio check is also a heuristic; it does not guarantee that a plate has only one text line.

### Targeted comparison results

The comparison used four previously inspected development examples and visually checked expected text. Both approaches received crops from the same trained YOLO model with the same padding and resizing. Exact match meant that every character in the normalized identifier matched the reference after removing separators. The EasyOCR baseline below includes the preprocessing improvements; the RapidOCR approach includes the conditional whole-crop fallback.

| Image | Expected identifier | Improved EasyOCR output | RapidOCR pipeline output |
|---|---|---|---|
| Cars281 | MH01DB0001 | MH010B0001 | MH01DB0001 |
| Cars320 | KA09MA2662 | KA09MA2662 | KA09MA2662 |
| Cars307 | M906090K | M906090K | M906090K |
| Cars323 | TN99F2378 | TN99F2378 | TN99F2378 |

EasyOCR matched 3 of the 4 examples, while the revised RapidOCR pipeline matched all 4. Cars281 used the whole-crop agreement fallback; the remaining examples used text-block detection and recognition. These results supported a provisional implementation decision to make RapidOCR the default.

These four examples were already inspected and used to guide development. Although the source files reside in a folder named test, they are not an untouched OCR test set after this tuning. The results must not be presented as 100 percent overall accuracy, a statistically reliable improvement, or a pure model-only comparison. The two pipelines also differ in preprocessing and fallback behaviour.

### Confidence and CPU processing time

| Image | EasyOCR score | RapidOCR score | EasyOCR time in seconds | RapidOCR time in seconds |
|---|---:|---:|---:|---:|
| Cars281 | 0.2686 | 0.9705 | 0.269 | 1.600 |
| Cars320 | 0.8403 | 0.9391 | 0.274 | 0.928 |
| Cars307 | 0.9949 | 0.9153 | 0.193 | 1.477 |
| Cars323 | 0.9995 | 0.9639 | 0.177 | 1.499 |

The measurements above come from the saved comparison run. They time OCR and text assembly for each crop, excluding the shared YOLO detection and crop preparation. Lazy model initialization may be included where it occurred. Each example was measured once, without repeated warm-up-controlled timing, so these values are indicative rather than a latency benchmark.

RapidOCR was slower in this run. We accepted that trade-off for the improved recognition on the observed failure case, while retaining sequential camera processing to avoid overlapping CPU inference requests. These crop timings do not measure complete live-camera frames per second.

The scores are internal model outputs, not probabilities that the complete plate is correct. They are not calibrated across engines. A higher RapidOCR score alone does not establish higher accuracy, and retaining the numerical threshold of 0.80 does not guarantee the same error rate for both engines. Wider validation and threshold calibration remain necessary.

### Integration and verification

RapidOCR became the default recognizer, while the SMARTPARK_OCR environment setting allows EasyOCR to be selected for comparison after a server restart. API responses identify the engine and recognition method. The parking database, automatic entry and exit rules, retained history, and Rs 10 per started minute tariff were not replaced by this OCR change.

After integration, 21 unit tests passed. They covered parking rules and billing as well as OCR block ordering, weak-fragment scores, fallback agreement and disagreement, and recognition-only output conversion. A read-only request to the running API returned Cars281 as MH01DB0001 with score 0.9705 and method whole_crop_agreement. The comparison and this API check did not alter parking records. Passing these tests verifies the specified software behaviour; it does not measure recognition accuracy on unseen images.

Earlier temporary-database tests separately verified automatic entry, exit and receipt generation. Camera-frame API tests verified stable readings, repeated-frame suppression and rearming after blank frames. Those tests should not be described as a completed physical webcam or phone-screen accuracy evaluation.

### Multiple vehicle limitation observed during demonstration

A subsequent screenshot of Cars311 showed two detected plates. The foreground red vehicle was read as TN21AT8349 with a displayed detection score of 81.5 percent and an OCR score rounded to 100.0 percent. The background white vehicle produced a detection score of 55.6 percent but no readable text. The unreadable result belonged to that second vehicle, not to the correctly recognized foreground plate. The displayed 100.0 percent score is rounded model confidence, not guaranteed correctness.

At the time of this screenshot, the automatic rule rejected an entire observation whenever more than one plate was detected, before checking individual recognition scores. Therefore, the correctly read foreground vehicle was not recorded from this image. This was a single-vehicle assumption and a limitation of event selection rather than evidence that the foreground OCR failed. Existing activity shown on the dashboard may belong to earlier successful scans.

Initially, an image containing only the intended plate was required to satisfy that assumption. A possible future improvement is a defined entry-lane region so that background vehicles do not block an intended scan. Such a rule would need testing and was not implemented as part of the experiments described here.

### Readable plate selection improvement

On 14 October 2026, we changed event selection to assess each detection before deciding whether an observation is ambiguous. When exactly one distinct plate satisfies the detection, OCR and identifier-format checks, that plate can create or close a session even if other detected plates are unreadable. Duplicate detections with the same accepted identifier count once. Two or more distinct readable identifiers still require a single-vehicle observation; no arbitrary vehicle is selected.

Unreadable background detections now show a neutral ignored-reading message when a readable plate is being processed. The camera still requires stable observations and suppresses repeated events while the same plate remains in view. An unreadable detection is not treated as a blank frame for rearming.

The updated suite passed 24 tests, including mixed readable and unreadable uploads, request retries, changing detection order in camera frames, repeated-frame suppression and duplicate boxes. This change concerns event selection and does not establish any increase in OCR accuracy.

### Remaining evaluation and conclusion

We started with EasyOCR, diagnosed specific failures, improved crop handling and text ordering, and then evaluated RapidOCR when a coloured plate remained difficult. RapidOCR combined with a conditional agreement-based fallback corrected that observed failure while preserving the other three development readings. The result was a useful improvement to the prototype, with increased CPU processing time and unresolved generalization risks.

Before making a final accuracy claim, we need a separately transcribed OCR evaluation set that is not used for prompt, preprocessing or threshold tuning. It should cover small plates, coloured backgrounds, stacked layouts, blur, glare, viewing angle and live phone-screen captures. Suitable measurements include full-plate exact-match rate, character error rate, accepted incorrect readings, skipped readings, complete entry-exit matching success, and repeated CPU latency measurements. YOLO detection precision and mAP must be reported separately from these OCR measures.

### Evidence and reproducibility

- [Saved OCR comparison results](../evidence/ocr_comparison.json)
- [Comparison script](../scripts/compare_ocr.py)
- [Experiment and verification notes](../evidence/README.md)
- [OCR engine and fallback implementation](../backend/ocr_engine.py)
- [Spatial text assembly implementation](../backend/ocr_text.py)
- [Automatic parking acceptance rules](../backend/automation.py)

Run the comparison from the project root with `.\.venv\Scripts\python.exe scripts\compare_ocr.py`. It requires the local model checkpoint, original images and installed requirements. It overwrites the saved comparison JSON, so retain the recorded run before producing new measurements for the final report.
