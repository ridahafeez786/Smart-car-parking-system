from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.utils import ImageReader
from PIL import Image
from pypdf import PdfReader
import pypdfium2 as pdfium

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/Smart_Parking_Report.pdf'
C=canvas.Canvas(str(OUT),pagesize=(612,792))
C.setTitle('Smart Parking System Project Report')
C.setAuthor('Rida Hafeez')
TEAL=HexColor('#087e80'); INK=HexColor('#183238'); GRAY=HexColor('#516269')
BODY=ParagraphStyle('body',fontName='Helvetica',fontSize=10.5,leading=15,textColor=INK)
SMALL=ParagraphStyle('small',parent=BODY,fontSize=8.5,leading=11,textColor=GRAY)
Y=0; PAGE=0

def para(text,x=48,width=516,style=BODY,gap=10):
 global Y
 p=Paragraph(text,style);w,h=p.wrap(width,700)
 assert Y-h>=45,(PAGE,text[:50],Y,h)
 p.drawOn(C,x,Y-h);Y-=h+gap

def head(text):
 global Y
 Y-=4;para(text,style=ParagraphStyle('h',parent=BODY,fontSize=12.5,leading=17,fontName='Helvetica-Bold'),gap=7)

def page(n,title):
 global Y,PAGE
 if n>1:C.showPage()
 PAGE=n
 C.setFillColor(TEAL);C.setFont('Helvetica-Bold',9);C.drawString(48,756,'SMART PARKING SYSTEM')
 C.setFillColor(GRAY);C.setFont('Helvetica',8);C.drawRightString(564,756,'Rida Hafeez | Capstone report')
 C.setStrokeColor(HexColor('#d5e1e3'));C.line(48,743,564,743)
 C.setFillColor(GRAY);C.setFont('Helvetica',8);C.drawString(48,28,'Development and evaluation | 14 October 2026');C.drawRightString(564,28,f'{n} / 5')
 Y=722;para(title,style=ParagraphStyle('title',parent=BODY,fontName='Helvetica-Bold',fontSize=22,leading=27,textColor=HexColor('#000000')),gap=14)

def table(rows,widths):
 global Y
 wrapped=[[Paragraph(str(v),ParagraphStyle('cell',parent=BODY,fontSize=9,leading=12,fontName='Helvetica-Bold' if i==0 else 'Helvetica')) for v in row] for i,row in enumerate(rows)]
 t=Table(wrapped,colWidths=widths)
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#e7f2f2')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.7,TEAL),('LINEBELOW',(0,1),(-1,-1),.3,HexColor('#dbe4e6'))]))
 w,h=t.wrap(516,700);assert Y-h>45;t.drawOn(C,48,Y-h);Y-=h+12

def image(path,x,top,width,height,region=None):
 # Clip source screenshots in the page layout without altering the source file.
 im=Image.open(path);iw,ih=im.size
 l,t,r,b=region or (0,0,iw,ih)
 scale=min(width/(r-l),height/(b-t));dw=(r-l)*scale;dh=(b-t)*scale
 xx=x+(width-dw)/2; yy=top-dh
 C.saveState();p=C.beginPath();p.rect(xx,yy,dw,dh);C.clipPath(p,stroke=0)
 C.drawImage(ImageReader(im),xx-l*scale,yy-(ih-b)*scale,width=iw*scale,height=ih*scale)
 C.restoreState();return xx,yy,scale

page(1,'Data collection and annotation')
para('We collected vehicle images from Kaggle and photographed parked cars ourselves. The aim was to build a smart parking prototype that reads a number plate, records an arrival, and calculates a charge when the same vehicle returns for exit.')
head('Preparing the labelled dataset')
para('We used Roboflow to annotate number plates with bounding boxes and export labels in YOLO format. Each label stores a class ID and normalized box coordinates: centre x, centre y, width and height. These labels teach the detector where a plate is; they do not contain its text.')
para('Before training, exact duplicate images were consolidated and annotations reconciled. Two visually confirmed missing boxes were added, and one image with no visible plate retained an empty label. Near-duplicates were not automatically checked. The original dataset and backup archive were preserved.')
table([['Split','Images','Plate boxes'],['Training','821','844'],['Validation','141','157'],['Test','199','274'],['Total','1,161','1,275']],[258,129,129])
head('Examples of the exported annotations')
top=Y
for i,name in enumerate(['Cars281','Cars323']):
 path=ROOT/f'Data Set Cleaned/test/images/{name}.png'
 xx,yy,scale=image(path,48+i*264,top,252,153)
 im=Image.open(path);iw,ih=im.size
 for line in (ROOT/f'Data Set Cleaned/test/labels/{name}.txt').read_text().splitlines():
  _,cx,cy,w,h=map(float,line.split());C.setStrokeColor(TEAL);C.setLineWidth(1.5);C.rect(xx+(cx-w/2)*iw*scale,yy+(1-cy-h/2)*ih*scale,w*iw*scale,h*ih*scale,fill=0)
Y=top-162
para('Figure 1. Sample dataset images with bounding boxes drawn from their saved YOLO labels. These are annotation examples, not model predictions.',style=SMALL)
para('The cleaned split counts are verified by the dataset audit. Exact source-wise counts and the Kaggle dataset URL were not recorded in that audit.',style=SMALL)

page(2,'Fine tuning YOLO11 on Colab')
para('Because the local laptop did not have a GPU, we trained the detector in Google Colab using a Tesla T4. We uploaded and extracted the cleaned dataset, checked the train, validation and test folders, and configured their paths in data.yaml.')
para('We initialized YOLO11n from pretrained weights and fine-tuned it for 30 epochs at an image size of 640 pixels with batch size 8. Training completed in 0.173 hours, approximately 10.4 minutes. The best checkpoint, best.pt, was downloaded for local CPU inference through FastAPI.')
head('Training evidence')
top=Y;image(ROOT/'evidence/yolo_training_epochs_and_validation.png',48,top,516,198,(225,570,1690,1038));Y=top-205
para('Figure 2. Colab output showing the final epoch, completed training run and validation of best.pt. This evidence relates to detector training.',style=SMALL)
head('Detector evaluation')
table([['Split','Precision','Recall','mAP 50','mAP 50–95'],['Validation','0.922','0.866','0.914','0.634'],['Test','0.938','0.763','0.824','0.575']],[140,94,94,94,94])
para('Validation used 141 images and 157 plate instances; the held-out detector test used 199 images and 274 instances. High test precision indicates relatively few false detections, while lower recall shows that some plates were missed. These measures evaluate plate localization, not the accuracy of reading the characters.')
para('After training, the local pipeline became: image or camera frame → YOLO plate box → cropped plate → OCR → parking session. Further detector tuning was not required for the OCR experiments described next.')

page(3,'OCR experiments and improvement')
para('We first used pretrained EasyOCR to read the YOLO crops. It correctly read several examples, but two cases exposed problems: a stacked plate prefix and white characters on a green background. We investigated preprocessing before selecting another engine.')
head('From EasyOCR to RapidOCR')
para('For Cars320, the initial text MA2662KAJ09 had incorrect ordering and a misread hyphen. Resizing alone did not consistently resolve it. We allowed hyphens during recognition, resized crops toward 400 pixels, used beam decoding, and ordered text blocks spatially before removing separators. The result became KA09MA2662. We used the lowest block score so a weak prefix could not be hidden by a strong suffix.')
para('EasyOCR still confused D with 0 on Cars281. We tested RapidOCR 3.10.0 with PP-OCRv6 models through ONNX Runtime 1.31.0 on the CPU. Its text detector initially missed the green crop; direct recognition of the whole plate succeeded. A fallback now requires original and inverted-grayscale readings to agree before accepting a wide, uncertain crop.')
top=Y
image(ROOT/'Data Set/test/images/Cars281.png',48,top,252,68,(148,161,247,194))
image(ROOT/'Data Set/test/images/Cars320.png',312,top,252,68,(60,195,275,278));Y=top-74
para('Figure 3. The green and stacked plates that motivated the OCR experiments, shown as enlarged crops from the original images.',style=SMALL)
table([['Image','Expected plate','EasyOCR','RapidOCR'],['Cars281','MH01DB0001','MH010B0001','MH01DB0001'],['Cars320','KA09MA2662','KA09MA2662','KA09MA2662'],['Cars307','M906090K','M906090K','M906090K'],['Cars323','TN99F2378','TN99F2378','TN99F2378']],[70,145,150,151])
para('The improved EasyOCR pipeline matched 3 of 4 examples; RapidOCR with the fallback matched all 4. CPU OCR times were about 0.18–0.27 seconds for EasyOCR and 0.93–1.60 seconds for RapidOCR in this run. Timings excluded YOLO and could include lazy initialization. We selected RapidOCR despite the speed trade-off.',gap=7)
para('These previously inspected examples guided development; this is not a held-out OCR benchmark or proof of 100% accuracy. Confidence scores are not calibrated probabilities. Neither OCR engine was fine-tuned.',style=SMALL)

page(4,'Building the parking application')
para('We connected the trained detector and OCR to a Python FastAPI backend and a browser dashboard built with HTML, CSS and JavaScript. SQLite stores parking sessions locally. The interface offers both image uploads and a live webcam preview, so the demonstration can use a phone displaying a plate image.')
head('Automatic entry and exit')
para('Selecting an image starts recognition automatically. If the accepted plate has no active visit, the system records its arrival using server time. If that plate already has an active visit, the next accepted appearance closes it, calculates the charge and creates a receipt. Completed visits leave the active list but remain in history.')
para('For the camera, three matching readings over at least two seconds are required. Holding a plate in view does not repeatedly toggle entry and exit. It must leave view until three blank readings span at least three seconds before the same plate can trigger again. Retried requests reuse event IDs to avoid duplicate database changes.')
top=Y;image(ROOT/'evidence/automatic_dashboard_test.jpg',48,top,516,263,(268,390,1228,1015));Y=top-270
para('Figure 4. Dashboard evidence showing live-camera controls and automatic activity. This screenshot predates the later readable-background selection rule.',style=SMALL)
head('Handling background vehicles')
para('Initially, an image with two detected plates was rejected even if one was readable. We changed the rule: exactly one distinct plate passing detection ≥0.50, OCR ≥0.80 and format checks is processed, while unreadable background plates are ignored. Two distinct readable plates remain ambiguous. Cars311 verified that TN21AT8349 could enter despite an unreadable plate behind it.')

page(5,'Billing verification and conclusion')
para('The configured tariff is Rs 10 per started minute, with a minimum of one minute. An exit after 60 seconds costs Rs 10; after 61 seconds it costs Rs 20. The rate is saved at entry. Earlier visits keep their original tariff. Receipts show the plate, arrival, departure, duration and amount, and can be printed or saved as PDF.')
head('Verification of the complete workflow')
top=Y
para('Image tests verified recognition, entry, exit and receipt generation using a temporary database. A recorded example produced a Rs 10 receipt after a 24-second visit. The tests did not represent real paid parking activity.',width=290)
para('The latest automated suite passed 24 tests covering billing boundaries, persistence, request retries, camera stability, OCR ordering, fallback agreement and readable-plate selection. A real-model test confirmed that Cars311 added its readable foreground plate once.',width=290)
para('Camera-frame API tests checked repeat suppression and rearming. A systematic physical webcam and phone-screen accuracy evaluation remains to be completed. Payment collection is not implemented.',width=290)
image(ROOT/'evidence/automatic_receipt_test.jpg',355,top,209,302,(390,532,873,1234))
Y=min(Y,top-310)
para('Figure 5. Saved test receipt at the minute tariff. History retains the completed visit.',style=SMALL)
head('Conclusion and remaining work')
para('The project progressed from mixed-source image collection and Roboflow labels to a Colab-trained detector and a working local parking application. OCR experiments improved difficult development examples and led to RapidOCR as the default. The prototype supports automatic visits and receipts on a CPU, but blur, glare, small text and competing readable plates can still prevent correct operation.')
para('Next, a separate transcribed OCR set should measure full-plate accuracy, character errors and incorrect accepted readings. Live tests should measure entry–exit matching and total processing time across lighting and viewing conditions. These checks are needed before making broader accuracy claims.',gap=8)
para('<b>Evidence:</b> dataset_audit.txt; Colab training screenshot; ocr_comparison.json and compare_ocr.py; dashboard and receipt captures; automated tests. All are retained in the project. Collection and Roboflow workflow are described by the project author.',style=SMALL)
C.save()
reader=PdfReader(str(OUT));assert len(reader.pages)==5,len(reader.pages)
pdf=pdfium.PdfDocument(str(OUT))
for i,p in enumerate(pdf):p.render(scale=1.35).to_pil().save(ROOT/f'tmp/report_qa/page-{i+1}.png')
print(f'Created {OUT} | {len(reader.pages)} pages')
