"""Local FastAPI service for license-plate detection with the trained YOLO model."""

from contextlib import asynccontextmanager
import os
from io import BytesIO
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from ultralytics import YOLO
from backend.parking import ParkingStore, router as parking_router
from backend.ocr_engine import PlateOCR


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEIGHTS_PATH = PROJECT_ROOT / "best.pt"
DATABASE_PATH = Path(os.environ.get("SMARTPARK_DB_PATH", str(PROJECT_ROOT / "storage" / "parking.sqlite3")))
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
INFERENCE_LOCK = RLock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not WEIGHTS_PATH.is_file():
        raise RuntimeError(f"Trained weights not found: {WEIGHTS_PATH}")
    app.state.model = YOLO(str(WEIGHTS_PATH))
    app.state.parking = ParkingStore(DATABASE_PATH)
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


def detect_image(file, confidence=0.25, include_ocr=False):
    """Return plate boxes in pixel coordinates for one uploaded image."""
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Upload an image file.")

    contents = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 12 MB or smaller.")
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    try:
        image = ImageOps.exif_transpose(Image.open(BytesIO(contents))).convert("RGB")
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
    if include_ocr and result.boxes is not None and len(result.boxes):
        reader = getattr(app.state, "ocr_reader", None)
        if reader is None:
            try:
                reader = PlateOCR()
            except Exception as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"OCR could not initialize ({type(exc).__name__}). Install backend/requirements.txt and restart the server.",
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
                scale = min(4, max(1, 400 / max(1, crop.width)))
                if scale > 1:
                    crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.Resampling.LANCZOS)
                try:
                    detection["ocr"] = reader.read(crop)
                except Exception as exc:
                    raise HTTPException(
                        status_code=503,
                        detail=f"OCR failed ({type(exc).__name__}). Try again or disable include_ocr.",
                    ) from exc
            detections.append(detection)

    return {
        "filename": file.filename,
        "image_width": image.width,
        "image_height": image.height,
        "count": len(detections),
        "ocr_enabled": include_ocr,
        "detections": detections,
    }


@app.post("/predict")
def predict(file: UploadFile = File(...), confidence: float = Query(0.25, ge=0.01, le=1), include_ocr: bool = False):
    with INFERENCE_LOCK:
        return detect_image(file, confidence, include_ocr)


@app.post("/parking/scan", tags=["Automatic parking"])
def automatic_scan(event_id: UUID, file: UploadFile = File(...),
                   source: Literal["upload", "camera"] = "upload", station_id: UUID | None = None):
    if source == "camera" and station_id is None:
        raise HTTPException(422, "Camera scans require a persistent station_id.")
    # Keep frame processing and gate updates ordered. Never accept browser-supplied OCR text.
    with INFERENCE_LOCK:
        prediction = detect_image(file, include_ocr=True)
        event = app.state.parking.auto_scan(prediction["detections"], str(event_id), source, str(station_id))
    return {**prediction, "event": event}
