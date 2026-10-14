"""CPU OCR engines with explicit provenance and a single-line fallback."""
import os
from backend.ocr_text import assemble


def rapid_parts(result, size):
    if not result.txts:
        return []
    boxes = getattr(result, 'boxes', None)
    if boxes is None:
        width, height = size
        boxes = [[[0,0],[width,0],[width,height],[0,height]]] * len(result.txts)
    return list(zip(boxes, result.txts, result.scores))


def agree_fallback(original, inverted):
    """Never select a reading just because its confidence is higher."""
    same = bool(original['normalized_text']) and original['normalized_text'] == inverted['normalized_text']
    result = dict(original)
    result['confidence'] = min(original['confidence'], inverted['confidence']) if same else 0.0
    result['needs_manual_review'] = not same or result['confidence'] < .80
    result['preprocessing_agreement'] = same
    return result


class PlateOCR:
    def __init__(self, engine=None):
        self.engine = engine or os.environ.get('SMARTPARK_OCR', 'rapidocr').lower()
        if self.engine == 'rapidocr':
            from rapidocr import RapidOCR
            # Keep enough detail for stacked plates without the default 736px
            # minimum side, which expands narrow crops to thousands of pixels.
            self.reader = RapidOCR(params={"Det.limit_type": "min", "Det.limit_side_len": 256})
        elif self.engine == 'easyocr':
            import easyocr
            self.reader = easyocr.Reader(['en'], gpu=False)
        else:
            raise ValueError('SMARTPARK_OCR must be rapidocr or easyocr')

    def read(self, crop):
        from PIL import ImageOps
        import numpy as np
        if self.engine == 'easyocr':
            parts = self.reader.readtext(np.asarray(crop), detail=1, paragraph=False,
                allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-', decoder='beamsearch', beamWidth=5)
            parsed = assemble(parts)
            parsed.update(engine='easyocr', method='text_blocks')
            return parsed
        # Set all flags on every call: RapidOCR retains call settings internally.
        result = self.reader(crop, use_det=True, use_cls=False, use_rec=True, text_score=0.0)
        parsed = assemble(rapid_parts(result, crop.size))
        parsed.update(engine='rapidocr', method='text_blocks')
        # Stacked layouts can need the original resolution. The service lock
        # serializes calls; always restore the fast setting for the next plate.
        if parsed['confidence'] < .80:
            detector = self.reader.text_det
            previous_limit = detector.limit_side_len
            try:
                detector.limit_side_len = 736
                result = self.reader(crop, use_det=True, use_cls=False, use_rec=True, text_score=0.0)
                parsed = assemble(rapid_parts(result, crop.size))
                parsed.update(engine='rapidocr', method='text_blocks_high_resolution')
            finally:
                detector.limit_side_len = previous_limit
        # Whole-crop recognition is suitable for wide, single-line candidates only.
        # Require the two image polarities to agree; do not guess D/O/0 mappings.
        if parsed['confidence'] < .80 and crop.width / max(1,crop.height) >= 2.5:
            original = assemble(rapid_parts(self.reader(crop,use_det=False,use_cls=False,use_rec=True,text_score=0.0),crop.size))
            inverted_crop = ImageOps.invert(ImageOps.grayscale(crop)).convert('RGB')
            inverted = assemble(rapid_parts(self.reader(inverted_crop,use_det=False,use_cls=False,use_rec=True,text_score=0.0),crop.size))
            fallback = agree_fallback(original,inverted)
            if not fallback['needs_manual_review']:
                fallback.update(engine='rapidocr', method='whole_crop_agreement')
                return fallback
        return parsed
