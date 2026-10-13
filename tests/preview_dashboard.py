"""Run the UI against a temporary database for browser checks."""
from contextlib import asynccontextmanager
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from backend.main import app, WEIGHTS_PATH
from backend.parking import ParkingStore
from ultralytics import YOLO
@asynccontextmanager
async def preview_lifespan(app):
    with TemporaryDirectory(prefix='smartpark_ui_test_') as directory:
        app.state.parking = ParkingStore(Path(directory) / 'test.sqlite3')
        app.state.model = YOLO(str(WEIGHTS_PATH))
        yield
if __name__ == '__main__':
    app.router.lifespan_context = preview_lifespan
    uvicorn.run(app, host='127.0.0.1', port=8001)
