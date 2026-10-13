'use strict';
const $ = id => document.getElementById(id);
const state = { mode: 'entry', tab: 'active', active: [], history: [], file: null, image: null, url: null, detections: [], selected: -1, busy: false, ready: false };
const money = minor => new Intl.NumberFormat('en-PK', { style: 'currency', currency: 'PKR', maximumFractionDigits: 0 }).format(minor / 100);
const date = value => new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Karachi', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
const normalize = value => value.toUpperCase().replace(/[\s.\-]/g, '');
const duration = seconds => { const minutes = Math.max(0, Math.floor(seconds / 60)); return minutes < 1 ? 'Less than a minute' : `${Math.floor(minutes / 60)}h ${minutes % 60}m`; };
function notify(message, error = false) { $('notice').textContent = message; $('notice').classList.toggle('error', error); $('notice').hidden = false; }
async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(Array.isArray(detail) ? detail.map(item => item.msg).join('; ') : detail || `Request failed (${response.status}).`);
  }
  return data;
}
function matchedSession() { return state.active.find(row => row.plate === normalize($('plate').value)); }
function updateForm() {
  const plate = normalize($('plate').value);
  const valid = /^[A-Z0-9]{3,15}$/.test(plate);
  const matched = matchedSession();
  $('save-visit').textContent = state.busy ? 'Please wait…' : state.mode === 'entry' ? 'Confirm entry' : 'Confirm exit & create receipt';
  $('save-visit').disabled = state.busy || !state.ready || !valid || !$('confirmed').checked || (state.mode === 'exit' ? !matched : Boolean(matched));
  $('match-note').textContent = state.mode === 'entry'
    ? matched ? 'This vehicle already has an active parking session.' : 'Confirm an arrival to start a parking session.'
    : matched ? `Active visit found · arrived ${date(matched.entry_time)}.` : plate ? 'No exact active match. Check the plate or select a vehicle below.' : 'Read or enter the departing vehicle’s plate.';
}
function setBusy(value) {
  state.busy = value;
  for (const id of ['entry-mode','exit-mode','image-file','plate','confirmed','refresh']) $(id).disabled = value;
  $('scan').disabled = value || !state.file || !state.image;
  document.querySelectorAll('.candidate,.row-action').forEach(el => { el.disabled = value; });
  updateForm();
}
function setMode(mode) {
  state.mode = mode; $('confirmed').checked = false;
  for (const item of ['entry','exit']) { $(`${item}-mode`).classList.toggle('chosen', item === mode); $(`${item}-mode`).setAttribute('aria-pressed', String(item === mode)); }
  updateForm();
}
function renderRecords() {
  const isActive = state.tab === 'active';
  const labels = isActive ? ['Plate','Arrival','Time parked','Action'] : ['Plate','Departure','Duration','Charge','Receipt'];
  const head = document.createElement('tr');
  for (const label of labels) { const th = document.createElement('th'); th.scope = 'col'; th.textContent = label; head.append(th); }
  $('table-head').replaceChildren(head);
  const filter = normalize($('search').value);
  const records = (isActive ? state.active : state.history).filter(row => row.plate.includes(filter));
  $('table-body').replaceChildren();
  for (const row of records) {
    const tr = document.createElement('tr');
    const values = isActive ? [row.plate, date(row.entry_time), duration((Date.now() - Date.parse(row.entry_time)) / 1000)] : [row.plate, date(row.exit_time), duration(row.duration_seconds), money(row.amount_minor)];
    for (const value of values) { const td = document.createElement('td'); td.textContent = value; tr.append(td); }
    const actionCell = document.createElement('td'); const button = document.createElement('button');
    button.className = 'row-action'; button.disabled = state.busy; button.textContent = isActive ? 'Check out →' : 'View receipt';
    button.addEventListener('click', () => {
      if (isActive) {
        setMode('exit'); $('plate').value = row.plate; $('confirmed').checked = false; updateForm(); $('plate').focus(); $('desk').scrollIntoView({ behavior: 'smooth', block: 'start' });
      } else openReceipt(row.id);
    });
    actionCell.append(button); tr.append(actionCell); $('table-body').append(tr);
  }
  $('empty-state').hidden = records.length > 0;
  $('empty-state').querySelector('h3').textContent = filter ? 'No matching plates' : isActive ? 'No vehicles parked yet' : 'No completed visits yet';
  $('empty-state').querySelector('p').textContent = filter ? 'Try a different plate number.' : isActive ? 'Confirm an entry above to start your first visit.' : 'A completed exit will appear here with its receipt.';
}
async function refresh() {
  try {
    const [active, history, summary, pricing] = await Promise.all(['/parking/active','/parking/history','/parking/summary','/parking/pricing'].map(path => api(path)));
    state.active = active; state.history = history; state.ready = true;
    $('active-count').textContent = summary.active_count; $('closed-count').textContent = summary.closed_count; $('total-charges').textContent = money(summary.total_amount_minor);
    $('rate').textContent = `${money(pricing.hourly_rate_minor)} / hour`;
    $('connection').textContent = '● Station online'; $('connection').className = 'pill online';
    renderRecords(); updateForm();
  } catch (error) {
    state.ready = false; $('connection').textContent = 'Station unavailable'; $('connection').className = 'pill offline'; updateForm();
    throw new Error(`Could not refresh records. Keep the server running, then click Refresh. ${error.message}`);
  }
}
function drawPhoto() {
  if (!state.image) return;
  const canvas = $('photo'); const scale = Math.min(1, 1200 / state.image.naturalWidth);
  canvas.width = Math.round(state.image.naturalWidth * scale); canvas.height = Math.round(state.image.naturalHeight * scale);
  const ctx = canvas.getContext('2d'); ctx.drawImage(state.image, 0, 0, canvas.width, canvas.height);
  state.detections.forEach((det, index) => {
    const [x1,y1,x2,y2] = det.box_xyxy.map(value => value * scale);
    ctx.strokeStyle = index === state.selected ? '#00ed9e' : '#ffd36c'; ctx.lineWidth = Math.max(2, canvas.width / 300); ctx.strokeRect(x1,y1,x2-x1,y2-y1);
    const label = String(index + 1); const size = Math.max(16, canvas.width / 35); ctx.fillStyle = ctx.strokeStyle; ctx.fillRect(x1, Math.max(0,y1-size-5), size+8, size+5); ctx.fillStyle = '#142d29'; ctx.font = `bold ${size}px sans-serif`; ctx.fillText(label,x1+4,Math.max(size,y1-4));
  });
}
function choosePlate(index) {
  state.selected = index; $('plate').value = state.detections[index].ocr?.normalized_text || ''; $('confirmed').checked = false;
  document.querySelectorAll('.candidate').forEach((el,i) => { el.classList.toggle('active', i === index); el.setAttribute('aria-pressed', String(i === index)); });
  drawPhoto(); updateForm();
}
$('image-file').addEventListener('change', async event => {
  state.file = null; state.image = null; state.detections = []; state.selected = -1; $('confirmed').checked = false; $('plate').value = ''; $('candidates').replaceChildren(); $('preview').hidden = true; $('scan').disabled = true; updateForm();
  if (state.url) URL.revokeObjectURL(state.url);
  const file = event.target.files[0]; if (!file) return;
  if (file.size > 12 * 1024 * 1024) { notify('Choose an image no larger than 12 MB.', true); return; }
  if (!['image/jpeg','image/png','image/webp'].includes(file.type)) { notify('Choose a JPG, PNG or WebP image.', true); return; }
  const image = new Image(); const url = URL.createObjectURL(file); state.url = url; image.src = url;
  try { await image.decode(); if (state.url !== url) return; state.image = image; state.file = file; $('filename').textContent = file.name; $('preview').hidden = false; $('scan').disabled = state.busy; $('scan-hint').textContent = 'Read the plate, then check the result on the right.'; drawPhoto(); }
  catch { if (state.url === url) notify('This image could not be opened. Try another image.', true); }
});
$('scan').addEventListener('click', async () => {
  if (state.busy || !state.file) return;
  setBusy(true); $('scan-progress').hidden = false; $('candidates').replaceChildren(); $('plate').value = ''; $('confirmed').checked = false; state.detections = []; state.selected = -1; drawPhoto();
  try {
    const form = new FormData(); form.append('file', state.file);
    const result = await api('/predict?include_ocr=true', { method: 'POST', body: form }); state.detections = result.detections;
    for (const [index, det] of state.detections.entries()) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'candidate';
      const text = document.createElement('span'); const title = document.createElement('strong'); const detail = document.createElement('small');
      title.textContent = `${index + 1}. ${det.ocr?.normalized_text || 'Text not readable'}`;
      detail.textContent = `Detection score ${(det.confidence * 100).toFixed(2)}% · OCR score ${((det.ocr?.confidence || 0) * 100).toFixed(2)}% · ${det.ocr?.needs_manual_review ? 'Check carefully' : 'Verify characters'}`;
      text.append(title,detail); const arrow = document.createElement('span'); arrow.textContent = '→'; button.append(text,arrow); button.addEventListener('click', () => choosePlate(index)); $('candidates').append(button);
    }
    if (state.detections.length === 1) choosePlate(0);
    else { drawPhoto(); $('plate').value = ''; }
    notify(result.count ? result.count === 1 ? 'Plate found. Check the characters and confirm the vehicle movement.' : `${result.count} plates found. Select the vehicle you want to record.` : 'No plate detected. Use a clearer photo or type the plate manually.');
  } catch (error) { notify(error.message, true); }
  finally { $('scan-progress').hidden = true; setBusy(false); }
});
$('entry-mode').addEventListener('click', () => setMode('entry'));
$('exit-mode').addEventListener('click', () => setMode('exit'));
$('plate').addEventListener('input', () => { $('confirmed').checked = false; updateForm(); });
$('confirmed').addEventListener('change', updateForm);
$('visit-form').addEventListener('submit', async event => {
  event.preventDefault(); if ($('save-visit').disabled) return;
  const plate = normalize($('plate').value); const mode = state.mode; const matched = matchedSession();
  if (mode === 'exit' && !matched) return;
  setBusy(true);
  try {
    const path = mode === 'entry' ? '/parking/entry' : `/parking/sessions/${encodeURIComponent(matched.id)}/exit`;
    const row = await api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ plate, confirmed: true }) });
    $('confirmed').checked = false;
    notify(mode === 'entry' ? `${row.plate} entered at ${date(row.entry_time)}. Parking session saved.` : `${row.plate} checked out. Parking charge: ${money(row.amount_minor)}.`);
    if (mode === 'exit') showReceipt(row);
    try { await refresh(); } catch (error) { notify(`Visit saved successfully. ${error.message}`, true); }
  } catch (error) { notify(`${error.message} Refresh records before retrying if the connection was interrupted.`, true); }
  finally { setBusy(false); }
});
function showReceipt(row) {
  $('receipt-content').replaceChildren();
  const rows = [['Plate',row.plate],['Receipt ID',row.id],['Entry',date(row.entry_time)],['Exit',date(row.exit_time)],['Time parked',duration(row.duration_seconds)],['Billed hours',String(row.billed_hours)],['Hourly rate',money(row.hourly_rate_minor)],['Total charge',money(row.amount_minor)]];
  for (const [key,value] of rows) { const line = document.createElement('div'); line.className = `receipt-row${key === 'Total charge' ? ' total' : ''}`; const label = document.createElement('span'); label.textContent = key; const content = document.createElement('strong'); content.textContent = value; line.append(label,content); $('receipt-content').append(line); }
  if (!$('receipt-dialog').open) $('receipt-dialog').showModal();
}
async function openReceipt(id) { try { showReceipt(await api(`/parking/sessions/${encodeURIComponent(id)}/receipt`)); } catch (error) { notify(error.message,true); } }
$('close-receipt').addEventListener('click', () => $('receipt-dialog').close());
$('print-receipt').addEventListener('click', () => window.print());
for (const tab of ['active','history']) $(`${tab}-tab`).addEventListener('click', () => { state.tab = tab; for (const name of ['active','history']) { $(`${name}-tab`).classList.toggle('current',name === tab); $(`${name}-tab`).setAttribute('aria-pressed',String(name === tab)); } renderRecords(); });
$('search').addEventListener('input',renderRecords);
$('refresh').addEventListener('click', async () => { $('refresh').disabled = true; try { await refresh(); notify('Parking records refreshed.'); } catch (error) { notify(error.message,true); } finally { $('refresh').disabled = state.busy; } });
$('clock').textContent = `${date(new Date())} · PKT`;
setInterval(() => { $('clock').textContent = `${date(new Date())} · PKT`; renderRecords(); }, 60000);
renderRecords(); refresh().catch(error => notify(error.message,true));
