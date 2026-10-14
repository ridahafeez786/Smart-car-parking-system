"""Targeted OCR regression comparison; not a held-out accuracy benchmark."""
import json
import sys
import time
from pathlib import Path
from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.ocr_text import assemble


def main():
    import easyocr
    from backend.ocr_engine import PlateOCR
    from ultralytics import YOLO
    model=YOLO(str(ROOT/'best.pt'))
    easy=easyocr.Reader(['en'],gpu=False)
    rapid=PlateOCR("rapidocr")
    rows=[]
    for name,truth in [('Cars281','MH01DB0001'),('Cars320','KA09MA2662'),('Cars307','M906090K'),('Cars323','TN99F2378')]:
        image=Image.open(ROOT/f'Data Set/test/images/{name}.png').convert('RGB')
        box=model.predict(image,device='cpu',verbose=False)[0].boxes.xyxy[0].tolist()
        x,y,r,b=map(lambda n:round(float(n),2),box)
        px=max(2,round((r-x)*.08));py=max(2,round((b-y)*.12))
        crop=image.crop((max(0,int(x)-px),max(0,int(y)-py),min(image.width,int(r)+px),min(image.height,int(b)+py)))
        scale=min(4,max(1,400/crop.width))
        crop=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.LANCZOS)
        for engine in ['easyocr','rapidocr']:
            start=time.perf_counter()
            if engine=='easyocr':
                parts=easy.readtext(np.asarray(crop),detail=1,paragraph=False,allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-',decoder='beamsearch',beamWidth=5)
            else:
                parsed=rapid.read(crop)
            if engine=='easyocr':
                parsed=assemble(parts)
            row={'image':name,'expected':truth,'engine':engine,**parsed,'exact_match':parsed['normalized_text']==truth,'seconds':round(time.perf_counter()-start,3)}
            rows.append(row);print(json.dumps(row),flush=True)
    (ROOT/'evidence/ocr_comparison.json').write_text(json.dumps({'scope':'Four previously inspected development examples, not an accuracy benchmark','results':rows},indent=2),encoding='utf-8')

if __name__=='__main__':main()
