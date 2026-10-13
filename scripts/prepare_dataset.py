from pathlib import Path
from collections import defaultdict, Counter
import csv, hashlib, shutil
from PIL import Image

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT / "Data Set"
OUTPUT = PROJECT / "Data Set Cleaned"
SPLITS = ("train", "val", "test")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
# Two verified missed annotations. Coordinates are YOLO normalized xywh.
MANUAL_LABELS = {
    ("train", "IMG_20211228_182815_jpg.rf.b3b908655f9d79f1a2f645f8d49d95bd.jpg"):
        ["0 0.507031 0.632812 0.204688 0.234375"],
    ("test", "IMG_20200122_160528_jpg.rf.298ef65519f34171cb87f37323326884.jpg"):
        ["0 0.944531 0.576562 0.098438 0.100000"],
}

if not SOURCE.is_dir():
    raise FileNotFoundError(f"Dataset folder not found: {SOURCE}")
if OUTPUT.exists():
    raise FileExistsError(f"Refusing to overwrite existing cleaned dataset: {OUTPUT}")

# Hash files, retaining annotation copies so duplicate annotations can be reconciled.
groups = defaultdict(list)
source_counts = {}
for split in SPLITS:
    image_dir = SOURCE / split / "images"
    label_dir = SOURCE / split / "labels"
    images = sorted(p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    source_counts[split] = len(images)
    for image in images:
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        label = label_dir / (image.stem + ".txt")
        if not label.is_file():
            raise ValueError(f"Missing label file for {image}")
        groups[digest].append((split, image, label))

# Prefer the held-out test sample, then validation, then training when an exact image
# occurs in several splits. This prevents that image from appearing in another split.
rank = {"test": 0, "val": 1, "train": 2}

def parse_label(label_path):
    text = label_path.read_text(encoding="utf-8-sig").strip()
    boxes = []
    for line_number, line in enumerate(text.splitlines(), 1):
        parts = line.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid YOLO row at {label_path}:{line_number}: {line}")
        cls, x, y, w, h = map(float, parts)
        if cls != 0 or not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
            raise ValueError(f"Invalid class or normalized box at {label_path}:{line_number}: {line}")
        if x-w/2 < -1e-5 or y-h/2 < -1e-5 or x+w/2 > 1.00001 or y+h/2 > 1.00001:
            raise ValueError(f"Box outside image at {label_path}:{line_number}: {line}")
        boxes.append((cls, x, y, w, h))
    return boxes

def iou(a, b):
    ax1, ay1, ax2, ay2 = a[1]-a[3]/2, a[2]-a[4]/2, a[1]+a[3]/2, a[2]+a[4]/2
    bx1, by1, bx2, by2 = b[1]-b[3]/2, b[2]-b[4]/2, b[1]+b[3]/2, b[2]+b[4]/2
    iw, ih = max(0.0, min(ax2,bx2)-max(ax1,bx1)), max(0.0, min(ay2,by2)-max(ay1,by1))
    inter = iw*ih
    return inter / max(1e-12, a[3]*a[4]+b[3]*b[4]-inter)

def reconcile(boxes):
    # Repeated labels for the same plate are clustered at IoU >= 0.40; use the
    # medoid annotation. Separate boxes remain when duplicate copies label
    # different plates in one image.
    clusters = []
    for box in boxes:
        eligible = [c for c in clusters if all(iou(box, member) >= 0.40 for member in c)]
        if eligible:
            eligible[0].append(box)
        else:
            clusters.append([box])
    out = []
    for cluster in clusters:
        if len(cluster) == 1:
            out.append(cluster[0])
        else:
            out.append(max(cluster, key=lambda a: sum(iou(a,b) for b in cluster)))
    return out

OUTPUT.mkdir(parents=True)
for split in SPLITS:
    (OUTPUT / split / "images").mkdir(parents=True)
    (OUTPUT / split / "labels").mkdir(parents=True)

manifest=[]
for digest, items in sorted(groups.items()):
    items = sorted(items, key=lambda item: (rank[item[0]], item[1].name))
    keeper_split, keeper_image, keeper_label = items[0]
    all_boxes=[]
    for split, image, label in items:
        override = MANUAL_LABELS.get((split, image.name))
        if override is not None:
            # Parse and validate handwritten verified coordinates.
            for line in override:
                cls,x,y,w,h=map(float,line.split()); all_boxes.append((cls,x,y,w,h))
        else:
            all_boxes.extend(parse_label(label))
    merged = reconcile(all_boxes)
    dest_image = OUTPUT / keeper_split / "images" / keeper_image.name
    dest_label = OUTPUT / keeper_split / "labels" / (keeper_image.stem + ".txt")
    shutil.copy2(keeper_image, dest_image)
    with dest_label.open("w", encoding="utf-8", newline="\n") as f:
        for cls,x,y,w,h in merged:
            f.write(f"{int(cls)} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n")
    manifest.append({"sha256":digest,"kept_split":keeper_split,"kept_image":keeper_image.name,
                     "copies_merged":len(items),"boxes_before_merge":len(all_boxes),"boxes_after_merge":len(merged),
                     "source_files":";".join(f"{s}/{p.name}" for s,p,_ in items)})

# Write portable local and Colab configurations, leaving both source configs untouched.
(OUTPUT / "data.yaml").write_text(
    f"path: '{OUTPUT.as_posix()}'\ntrain: train/images\nval: val/images\ntest: test/images\nnc: 1\nnames: ['license_plate']\n",
    encoding="utf-8")
(OUTPUT / "data_colab.yaml").write_text(
    "path: '/content/Data Set Cleaned'\ntrain: train/images\nval: val/images\ntest: test/images\nnc: 1\nnames: ['license_plate']\n",
    encoding="utf-8")
with (OUTPUT / "dedup_manifest.csv").open("w", newline="", encoding="utf-8") as f:
    writer=csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
    writer.writeheader();writer.writerows(manifest)

# Summarize clean counts and verify one-to-one image/label pairing and no hash leakage.
report=[]; output_hashes={}
for split in SPLITS:
    images=sorted(p for p in (OUTPUT/split/"images").iterdir() if p.is_file())
    labels=sorted((OUTPUT/split/"labels").glob("*.txt"))
    if len(images)!=len(labels) or {p.stem for p in images}!={p.stem for p in labels}:
        raise RuntimeError(f"Image/label pairing mismatch in {split}")
    boxes_count=empty_count=0
    for image in images:
        with Image.open(image) as im:
            im.verify()
        label=OUTPUT/split/"labels"/(image.stem+".txt")
        b=parse_label(label)
        boxes_count+=len(b)
        empty_count+=not bool(b)
        digest=hashlib.sha256(image.read_bytes()).hexdigest()
        if digest in output_hashes:
            raise RuntimeError(f"Duplicate remains across/within splits: {image} and {output_hashes[digest]}")
        output_hashes[digest]=f"{split}/{image.name}"
    report.append(f"{split}: {len(images)} images, {boxes_count} plate boxes, {empty_count} empty labels")
(OUTPUT/"DATASET_REPORT.txt").write_text(
    "Prepared from the original dataset; original files and Data Set.rar backup were not modified.\n"
    "Exact byte-identical image copies were consolidated. When a duplicate occurred across splits, the test copy was preferred, then validation, then train; annotations from copies were reconciled.\n"
    "Two visually confirmed missing plate boxes were added. One empty label remains as a valid no-visible-plate example.\n"
    "Near-duplicate images were not automatically detected. Plate text is not included; this dataset trains detection only.\n\n"
    + "\n".join(report)+"\n", encoding="utf-8")
print("Created:", OUTPUT)
print("Input images:", source_counts, "total", sum(source_counts.values()))
print("Exact duplicate groups:", sum(1 for x in manifest if x["copies_merged"]>1))
print("Removed exact duplicate copies:", sum(x["copies_merged"]-1 for x in manifest))
print("Manual annotations added:",len(MANUAL_LABELS))
print("Output:","; ".join(report))
print("Configs:",OUTPUT/"data.yaml",OUTPUT/"data_colab.yaml")
