"""Local FastAPI service for license-plate detection with the trained YOLO model."""

from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
import re

import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from ultralytics import YOLO
from backend.parking import ParkingStore, router as parking_router


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEIGHTS_PATH = PROJECT_ROOT / "best.pt"
MAX_UPLOAD_BYTES = 12 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not WEIGHTS_PATH.is_file():
        raise RuntimeError(f"Trained weights not found: {WEIGHTS_PATH}")
    app.state.model = YOLO(str(WEIGHTS_PATH))
    app.state.parking = ParkingStore(PROJECT_ROOT / "storage" / "parking.sqlite3")
    yield


app = FastAPI(
    title="Smart Parking API",
    description="Detect license plates using the project-trained YOLO model.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(parking_router)
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "backend" / "static"), name="static")


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(PROJECT_ROOT / "backend" / "static" / "index.html")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": getattr(app.state, "model", None) is not None,
        "weights_file": WEIGHTS_PATH.name,
    }


@app.post("/predict")
def predict(
    file: UploadFile = File(...),
    confidence: float = Query(default=0.25, ge=0.01, le=1.0),
    include_ocr: bool = Query(default=False),
):
    """Return plate boxes in pixel coordinates for one uploaded image."""
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Upload an image file.")

    contents = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 12 MB or smaller.")
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    try:
        image = Image.open(BytesIO(contents)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="The uploaded file is not a readable image.")

    result = app.state.model.predict(
        source=image,
        device="cpu",
        imgsz=640,
        conf=confidence,
        verbose=False,
    )[0]

    reader = None
    if include_ocr:
        reader = getattr(app.state, "ocr_reader", None)
        if reader is None:
            try:
                import easyocr
            except ImportError:
                raise HTTPException(
                    status_code=503,
                    detail="OCR is not installed. Install backend/requirements.txt and restart the API.",
                )
            try:
                reader = easyocr.Reader(["en"], gpu=False)
            except Exception as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"OCR could not initialize ({type(exc).__name__}). Check internet access for its first model download, then retry.",
                ) from exc
            app.state.ocr_reader = reader

    detections = []
    if result.boxes is not None:
        for box in result.boxes:
            x1, y1, x2, y2 = (round(float(value), 2) for value in box.xyxy[0].tolist())
            class_id = int(box.cls[0])
            detection = {
                "label": result.names.get(class_id, str(class_id)),
                "confidence": round(float(box.conf[0]), 4),
                "box_xyxy": [x1, y1, x2, y2],
            }
            if reader is not None:
                left, top, right, bottom = x1, y1, x2, y2
                pad_x = max(2, round((right - left) * 0.08))
                pad_y = max(2, round((bottom - top) * 0.12))
                left = max(0, int(left) - pad_x)
                top = max(0, int(top) - pad_y)
                right = min(image.width, int(right) + pad_x)
                bottom = min(image.height, int(bottom) + pad_y)
                crop = image.crop((left, top, right, bottom))
                scale = min(4, max(1, round(300 / max(1, crop.width))))
                if scale > 1:
                    crop = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.LANCZOS)
                try:
                    ocr_parts = reader.readtext(
                        np.asarray(crop),
                        detail=1,
                        paragraph=False,
                        allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                    )
                except Exception as exc:
                    raise HTTPException(
                        status_code=503,
                        detail=f"OCR failed ({type(exc).__name__}). Try again or disable include_ocr.",
                    ) from exc
                raw_text = " ".join(part[1] for part in ocr_parts).strip()
                normalized_text = re.sub(r"[^A-Z0-9]", "", raw_text.upper())
                ocr_confidences = [float(part[2]) for part in ocr_parts]
                ocr_score = sum(ocr_confidences) / len(ocr_confidences) if ocr_confidences else 0.0
                detection["ocr"] = {
                    "raw_text": raw_text,
                    "normalized_text": normalized_text,
                    "confidence": round(ocr_score, 4),
                    "needs_manual_review": not normalized_text or ocr_score < 0.65,
                }
            detections.append(detection)

    return {
        "filename": file.filename,
        "image_width": image.width,
        "image_height": image.height,
        "count": len(detections),
        "ocr_enabled": reader is not None,
        "detections": detections,
    }
