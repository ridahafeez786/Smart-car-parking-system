'use strict';
const $ = id => document.getElementById(id);
const state = { source:'image', tab:'active', active:[], history:[], busy:false, running:false, stream:null, timer:null, job:null, image:null, url:null, receipt:null, generation:0, events:new Set() };
const money = n => new Intl.NumberFormat('en-PK',{style:'currency',currency:'PKR',maximumFractionDigits:0}).format(n/100);
const date = v => new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Karachi',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(v));
const duration = n => { n=Math.max(0,Math.floor(n)); return `${Math.floor(n/3600)}h ${Math.floor(n/60)%60}m ${n%60}s`; };
function notify(text,error=false){ $('notice').textContent=text; $('notice').hidden=false; $('notice').classList.toggle('error',error); }
async function api(path,options={}){ const r=await fetch(path,options); const d=await r.json().catch(()=>({})); if(!r.ok){const e=new Error(typeof d.detail==='string'?d.detail:`Request failed (${r.status})`);e.status=r.status;throw e;} return d; }
function controls(){
  $('image-file').disabled=state.busy||state.running||Boolean(state.job);
  $('scan').disabled=state.busy||state.running||!state.job||state.job.source!=='upload';
  $('camera-start').disabled=state.running||state.busy;
  $('camera-stop').disabled=!state.running;
  $('camera-select').disabled=state.running||state.busy;
  for(const id of ['source-image','source-camera'])$(id).disabled=state.busy;
  $('scan-progress').hidden=!state.busy;
}
function renderRecords(){
  const active=state.tab==='active'; const head=document.createElement('tr');
  for(const title of active?['Plate','Arrival','Time parked','Status']:['Plate','Departure','Duration','Charge','Receipt']){const th=document.createElement('th');th.textContent=title;head.append(th);}
  $('table-head').replaceChildren(head); $('table-body').replaceChildren();
  const filter=$('search').value.toUpperCase().replace(/[\s.-]/g,'');
  const rows=(active?state.active:state.history).filter(r=>r.plate.includes(filter));
  for(const row of rows){const tr=document.createElement('tr');
    for(const value of active?[row.plate,date(row.entry_time),duration((Date.now()-Date.parse(row.entry_time))/1000)]:[row.plate,date(row.exit_time),duration(row.duration_seconds),money(row.amount_minor)]){const td=document.createElement('td');td.textContent=value;tr.append(td);}
    const td=document.createElement('td');
    if(active){td.textContent='Parked';td.className='row-status';}else{const b=document.createElement('button');b.className='row-action';b.textContent='View receipt';b.onclick=()=>api(row.receipt_url).then(showReceipt).catch(e=>notify(e.message,true));td.append(b);}
    tr.append(td);$('table-body').append(tr);
  }
  $('empty-state').hidden=rows.length>0;
  $('empty-state').querySelector('h3').textContent=filter?'No matching plates':active?'No vehicles parked yet':'No completed visits yet';
  $('empty-state').querySelector('p').textContent='Show or upload a clear plate to record an event automatically.';
}
async function refresh(){
  const [active,history,summary,pricing]=await Promise.all(['/parking/active','/parking/history','/parking/summary','/parking/pricing'].map(p=>api(p)));
  Object.assign(state,{active,history}); $('active-count').textContent=summary.active_count; $('closed-count').textContent=summary.closed_count; $('total-charges').textContent=money(summary.total_amount_minor); $('rate').textContent=`${money(pricing.minute_rate_minor)} / minute`;
  $('connection').textContent='● Station online';$('connection').className='pill online';renderRecords();
}
function draw(result,source){
  const canvas=$(source==='camera'?'camera-overlay':'photo'); canvas.width=result.image_width;canvas.height=result.image_height;const ctx=canvas.getContext('2d');
  if(source==='upload'&&state.image)ctx.drawImage(state.image,0,0,canvas.width,canvas.height);
  ctx.strokeStyle='#00ed9e';ctx.lineWidth=Math.max(2,canvas.width/300);
  for(const det of result.detections){const [x,y,x2,y2]=det.box_xyxy;ctx.strokeRect(x,y,x2-x,y2-y);}
  $('candidates').replaceChildren();
  for(const det of result.detections){const card=document.createElement('div');card.className='candidate';const text=document.createElement('span');const title=document.createElement('strong');title.textContent=det.ocr?.normalized_text||'Text unreadable';const detail=document.createElement('small');detail.textContent=`${det.ocr?.engine || 'OCR'} · Detection ${(det.confidence*100).toFixed(1)}% · OCR ${((det.ocr?.confidence||0)*100).toFixed(1)}%`;text.append(title,detail);if(det.confidence<.50||(det.ocr?.confidence||0)<.80){const reason=document.createElement('small');reason.textContent=result.event?.plate?'Background reading ignored. The readable plate is processed separately.':'Not recorded: requires detection ≥50% and OCR ≥80%. Try a clearer, closer image.';text.append(reason);}card.append(text);$('candidates').append(card);}
}
function showEvent(event,id){
  const messages={empty:'No plate found. Show a clearer image.',multiple:'More than one readable plate found. Show one vehicle at a time.',uncertain:'Reading unclear. Move closer and hold steady.',ready:'Ready · show a plate.',rearming:'Keep the plate out of view until Ready appears.',already_seen:'Already recorded. Remove the plate until Ready, then show it again.',stabilizing:`Reading ${event.plate} · ${Math.min(event.stable_readings||0,3)}/3 stable frames…`};
  $('scanner-state').textContent=messages[event.status]||'Plate processed.';
  if(!event.action){if(['empty','multiple','uncertain'].includes(event.status))notify(`Vehicle not added or removed. ${messages[event.status]}`,true);else $('notice').hidden=true;return;}
  if(state.events.has(id))return;
  state.events.add(id);const row=event.session;
  const text=event.action==='entry'?`${row.plate} entered at ${date(row.entry_time)}.`:`${row.plate} exited · ${money(row.amount_minor)} · ${duration(row.duration_seconds)}.`;
  $('scanner-state').textContent=text;$('last-plate').textContent=row.plate;$('last-event').textContent=text;notify(text);
  if(state.events.size===1)$('activity-log').replaceChildren();const li=document.createElement('li');li.textContent=text;$('activity-log').prepend(li);while($('activity-log').children.length>8)$('activity-log').lastChild.remove();
  if(event.action==='exit'){state.receipt=row;$('last-receipt').hidden=false;}
}
async function submitJob(){
  if(state.busy||!state.job)return;const job=state.job;state.busy=true;controls();
  try{
    const form=new FormData();form.append('file',job.file,job.file.name||'camera.jpg');
    const query=new URLSearchParams({source:job.source,event_id:job.id});if(job.station)query.set('station_id',job.station);
    const result=await api(`/parking/scan?${query}`,{method:'POST',body:form});
    state.job=null;draw(result,job.source);showEvent(result.event,job.id);
    if(result.event.action)await refresh().catch(e=>notify(`Event saved. Could not refresh records: ${e.message}`,true));
  }catch(e){const invalid=e.status>=400&&e.status<500;if(invalid)state.job=null;notify(invalid?e.message:`Scan interrupted: ${e.message}. Retrying uses the same event to prevent duplicates.`,true);$('scanner-state').textContent=invalid?'Image rejected. Choose another image.':'Connection interrupted. Waiting to retry.';}
  finally{state.busy=false;controls();}
}
$('image-file').addEventListener('change',async e=>{
  const file=e.target.files[0];e.target.value='';if(!file||state.busy)return;
  if(file.size>12*1024*1024||!['image/jpeg','image/png','image/webp'].includes(file.type)){notify('Choose a JPG, PNG or WebP image up to 12 MB.',true);return;}
  state.busy=true;controls();if(state.url)URL.revokeObjectURL(state.url);state.url=URL.createObjectURL(file);const image=new Image();image.src=state.url;
  try{await image.decode();state.image=image;$('preview').hidden=false;$('filename').textContent=file.name;draw({image_width:image.naturalWidth,image_height:image.naturalHeight,detections:[]},'upload');state.job={source:'upload',file,id:crypto.randomUUID()};}
  catch(e){notify('Could not open this image.',true);state.job=null;}
  finally{state.busy=false;controls();}await submitJob();
});
$('scan').onclick=submitJob;
function stopCamera(){state.generation++;state.running=false;clearTimeout(state.timer);if(state.stream)state.stream.getTracks().forEach(t=>t.stop());state.stream=null;$('camera-video').srcObject=null;$('camera-placeholder').hidden=false;controls();}
for(const source of ['image','camera'])$(`source-${source}`).onclick=()=>{
  if(state.busy)return;if(source==='image')stopCamera();$('candidates').replaceChildren();state.source=source;$('upload-content').hidden=source!=='image';$('live-content').hidden=source!=='camera';
  for(const s of ['image','camera']){$(`source-${s}`).classList.toggle('chosen',s===source);$(`source-${s}`).setAttribute('aria-pressed',String(s===source));}
};
async function cameraLoop(){
  if(!state.running)return;
  try{
    if(!state.job){const video=$('camera-video');if(!video.videoWidth)throw new Error('Camera has not provided a frame yet.');const canvas=document.createElement('canvas');const scale=Math.min(1,1280/video.videoWidth);canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.9));if(!blob)throw new Error('Could not capture camera frame.');if(!state.running)return;state.job={source:'camera',file:blob,id:crypto.randomUUID(),station:state.station};}
    await submitJob();
  }catch(e){notify(e.message,true);}
  if(state.running)state.timer=setTimeout(cameraLoop,1000);
}
$('camera-start').onclick=async()=>{
  if(state.busy||state.running)return;
  try{
    if(!navigator.mediaDevices?.getUserMedia)throw new Error('Camera requires localhost or HTTPS. Open this app at http://127.0.0.1:8000 on your laptop.');
    state.station=localStorage.getItem('smartpark.station.id')||crypto.randomUUID();localStorage.setItem('smartpark.station.id',state.station);
    state.running=true;const generation=++state.generation;controls();const device=$('camera-select').value;
    const stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{width:{ideal:1280},height:{ideal:720},...(device?{deviceId:{exact:device}}:{facingMode:'environment'})}});
    if(!state.running||generation!==state.generation){stream.getTracks().forEach(t=>t.stop());return;}state.stream=stream;$('camera-video').srcObject=stream;await $('camera-video').play();if(!state.running||generation!==state.generation)return;$('camera-placeholder').hidden=true;
    const devices=await navigator.mediaDevices.enumerateDevices();$('camera-select').replaceChildren(new Option('Default camera',''));for(const d of devices.filter(d=>d.kind==='videoinput'))$('camera-select').add(new Option(d.label||'Camera',d.deviceId));$('camera-select').value=device;
    stream.getVideoTracks()[0].addEventListener('ended',()=>{stopCamera();notify('Camera disconnected. Reconnect it and start again.',true);});cameraLoop();
  }catch(e){stopCamera();notify(`Cannot start camera: ${e.message}. Allow camera access and close other apps using it.`,true);}
};
$('camera-stop').onclick=stopCamera;window.addEventListener('pagehide',stopCamera);
function showReceipt(row){
  $('receipt-content').replaceChildren();const minute=row.rate_unit==='minute';
  for(const [key,value] of [['Plate',row.plate],['Receipt ID',row.id],['Entry',date(row.entry_time)],['Exit',date(row.exit_time)],['Time parked',duration(row.duration_seconds)],[minute?'Billed minutes':'Billed hours',minute?row.billed_minutes:row.billed_hours],['Rate',`${money(row.unit_rate_minor)} / ${row.rate_unit}`],['Total charge',money(row.amount_minor)]]){const line=document.createElement('div');line.className=`receipt-row${key==='Total charge'?' total':''}`;const label=document.createElement('span');label.textContent=key;const val=document.createElement('strong');val.textContent=value;line.append(label,val);$('receipt-content').append(line);}
  $('receipt-policy').textContent=`Charged per started ${row.rate_unit}, minimum one. Tariff saved at entry. Payment collection is not tracked.`;if(!$('receipt-dialog').open)$('receipt-dialog').showModal();
}
$('last-receipt').onclick=()=>showReceipt(state.receipt);$('close-receipt').onclick=()=>$('receipt-dialog').close();$('print-receipt').onclick=()=>window.print();
for(const tab of ['active','history'])$(`${tab}-tab`).onclick=()=>{state.tab=tab;for(const t of ['active','history']){$(`${t}-tab`).classList.toggle('current',t===tab);$(`${t}-tab`).setAttribute('aria-pressed',String(t===tab));}renderRecords();};
$('search').oninput=renderRecords;$('refresh').onclick=()=>refresh().catch(e=>notify(e.message,true));
function tick(){$('clock').textContent=`${date(new Date())} · PKT`;renderRecords();}setInterval(tick,1000);tick();controls();refresh().catch(e=>{notify(e.message,true);$('connection').textContent='Station unavailable';});
