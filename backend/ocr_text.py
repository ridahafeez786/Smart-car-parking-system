"""Arrange OCR blocks spatially before normalizing a plate identifier."""
import re


def reading_order(parts):
    if len(parts) < 2:
        return list(parts)
    # Split complete rows first. If a tall suffix spans stacked prefix rows,
    # split columns instead, then read the prefix from top to bottom.
    for axis in (1, 0):
        ordered = sorted(parts, key=lambda p: min(point[axis] for point in p[0]))
        edge = max(point[axis] for point in ordered[0][0])
        for index in range(1, len(ordered)):
            start = min(point[axis] for point in ordered[index][0])
            if start > edge:
                return reading_order(ordered[:index]) + reading_order(ordered[index:])
            edge = max(edge, max(point[axis] for point in ordered[index][0]))
    return sorted(parts, key=lambda p: (sum(point[1] for point in p[0])/len(p[0]), min(point[0] for point in p[0])))


def assemble(parts):
    ordered = reading_order(parts)
    raw = ' '.join(p[1] for p in ordered).strip()
    normalized = re.sub(r'[^A-Z0-9]', '', raw.upper())
    # One poorly read prefix must not be hidden by a confidently read suffix.
    score = min((float(p[2]) for p in ordered), default=0.0)
    return {'raw_text': raw, 'normalized_text': normalized, 'confidence': round(score,4),
            'needs_manual_review': not normalized or score < 0.80}
