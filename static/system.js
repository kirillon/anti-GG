"use strict";
let systemResult = null;
let systemRequest = 0;
function invalidateSystem() {
  systemRequest++;
  systemResult = null;
  $("system-result").hidden = true;
  $("copy-status").textContent = "";
}
function refreshInputs() {
  const rows = [...$("system-inputs").children];
  rows.forEach((row, i) => {
    row.querySelector('label').textContent = `F${i+1} — единичные наборы`;
    row.querySelector('label').htmlFor = `system-function-${i+1}`;
    row.querySelector('input').id = `system-function-${i+1}`;
    row.querySelector('button').disabled = rows.length <= 2;
    row.querySelector('button').setAttribute('aria-label', `Удалить F${i+1}`);
  });
  $("add-function").disabled = rows.length >= 4;
}
function addFunction(value = "") {
  if ($("system-inputs").children.length >= 4) return;
  const row = document.createElement('div'); row.className = 'function-row';
  const label = document.createElement('label');
  const input = document.createElement('input'); input.type = 'text'; input.value = value;
  input.maxLength = 256; input.placeholder = 'Например: 0, 2, 4, 6';
  input.addEventListener('input', invalidateSystem);
  const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '−';
  remove.addEventListener('click', () => {row.remove(); refreshInputs(); invalidateSystem();});
  row.append(label, input, remove); $("system-inputs").append(row); refreshInputs(); invalidateSystem();
}
for (const value of ['0, 2, 4, 6, 10, 12, 14', '2, 3, 10', '0, 1, 2, 3, 9, 11']) addFunction(value);
$("add-function").addEventListener('click', () => addFunction());
$("variable-count").addEventListener('change', invalidateSystem);
for (const mode of ['single', 'system']) $(mode+'-tab').addEventListener('click', () => {
  for (const other of ['single', 'system']) {
    $(other+'-section').hidden = other !== mode;
    $(other+'-tab').setAttribute('aria-pressed', String(other === mode));
  }
});
function renderMaps(id, maps) {
  $(id).replaceChildren();
  for (const map of maps) {
    const card = document.createElement('article'); card.className = 'card map-card';
    // The server builds and escapes all SVG text from validated numerical inputs.
    card.innerHTML = map.svg;
    const save = document.createElement('button'); save.textContent = `↓ SVG ${map.name}`;
    save.addEventListener('click', () => download(new Blob([map.svg], {type:'image/svg+xml'}), map.name.replaceAll(' · ', '-')+'.svg'));
    card.append(save); $(id).append(card);
  }
}
$("system-form").addEventListener('submit', async event => {
  event.preventDefault(); invalidateSystem();
  const id = systemRequest;
  $("system-error").hidden = true; $("system-submit").disabled = true;
  try {
    const response = await fetch('/api/system', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({variables:Number($("variable-count").value),
        functions:[...$("system-inputs").querySelectorAll('input')].map(input => input.value)})});
    const data = await response.json();
    if (id !== systemRequest) return;
    if (!response.ok) throw new Error(data.error || 'Ошибка расчёта');
    systemResult = data;
    $("sheffer-gates").replaceChildren(); $("sheffer-outputs").replaceChildren();
    for (const item of data.sheffer.gates) {
      const p = document.createElement('p'); p.textContent = `${item.name} = ${item.expression}`; $('sheffer-gates').append(p);
    }
    for (const item of data.sheffer.outputs) {
      const p = document.createElement('p');
      p.append(document.createTextNode(`${item.name} = `));
      const formula = document.createElement('span');
      // Formula markup is generated from validated variable names and escaped on the server.
      formula.innerHTML = item.formula_html; p.append(formula); $('sheffer-outputs').append(p);
    }
    $('sheffer-diagram').innerHTML = data.sheffer.svg;
    $('sheffer-zoom').value = '100'; resizeCircuit();
    $("sheffer-status").textContent = '';
    $("system-cost").textContent = `Букв в общей совокупности: ${data.literal_count}. Общих термов: ${data.term_count}. Минимум найден точным методом меток.`;
    $("system-formulas").replaceChildren();
    for (const output of data.outputs) {
      const p = document.createElement('p'); p.textContent = `${output.name} = ${output.formula}`;
      $("system-formulas").append(p);
    }
    $("system-matrix").innerHTML = data.matrix_html;
    renderMaps('system-output-maps', data.outputs); renderMaps('system-product-maps', data.products);
    $("system-result").hidden = false;
  } catch (error) {
    if (id === systemRequest) {$("system-error").textContent = error.message; $("system-error").hidden = false;}
  } finally {$("system-submit").disabled = false;}
});

function resizeCircuit() {
  const svg = $('sheffer-diagram').querySelector('svg');
  const scale = Number($('sheffer-zoom').value) / 100;
  $('sheffer-zoom-value').textContent = `${Math.round(scale * 100)}%`;
  if (svg) {svg.style.width = `${svg.viewBox.baseVal.width * scale}px`; svg.style.height = 'auto';}
}
$('sheffer-zoom').addEventListener('input', resizeCircuit);
$('sheffer-svg').addEventListener('click', () => {
  if (systemResult) download(new Blob([systemResult.sheffer.svg], {type:'image/svg+xml;charset=utf-8'}), 'sheffer-system.svg');
});
$('sheffer-png').addEventListener('click', async () => {
  if (!systemResult) return;
  const button = $('sheffer-png'); button.disabled = true;
  const url = URL.createObjectURL(new Blob([systemResult.sheffer.svg], {type:'image/svg+xml;charset=utf-8'}));
  try {
    const img = new Image(); img.src = url; await img.decode();
    const canvas = document.createElement('canvas');
    // Keep the complete diagram within browser canvas limits, including large systems.
    const scale = Math.min(2, 8192 / Math.max(img.naturalWidth, img.naturalHeight),
      Math.sqrt(16000000 / (img.naturalWidth * img.naturalHeight)));
    canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
    canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
    if (!blob) throw new Error('Не удалось сохранить PNG схемы.');
    download(blob, 'sheffer-system.png'); $('sheffer-status').textContent = 'PNG схемы подготовлен.';
  } catch (error) { $('sheffer-status').textContent = error.message; }
  finally {URL.revokeObjectURL(url); button.disabled = false;}
});
$("copy-matrix").addEventListener('click', async () => {
  if (!systemResult) return;
  try {
    if (navigator.clipboard?.write && window.ClipboardItem) {
      await navigator.clipboard.write([new ClipboardItem({
        'text/html':new Blob([systemResult.matrix_html], {type:'text/html'}),
        'text/plain':new Blob([systemResult.matrix_tsv], {type:'text/plain'})})]);
    } else {
      const range = document.createRange(); range.selectNodeContents($("system-matrix"));
      const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
      if (!document.execCommand('copy')) throw new Error('Копирование недоступно');
      selection.removeAllRanges();
    }
    $("copy-status").textContent = 'Таблица скопирована. Вставьте в Word: Ctrl+V.';
  } catch {
    $("copy-status").textContent = 'Браузер не разрешил копирование. Выделите таблицу и нажмите Ctrl+C или скачайте HTML.';
  }
});
$("download-matrix").addEventListener('click', () => {
  if (systemResult) download(new Blob(['<!doctype html><html lang="ru"><meta charset="utf-8"><title>Импликантная матрица</title><body>'+systemResult.matrix_html+'</body></html>'],
    {type:'text/html;charset=utf-8'}), 'implicant-matrix.html');
});

$("copy-sheffer").addEventListener('click', async () => {
  if (!systemResult) return;
  try {await navigator.clipboard.writeText(systemResult.sheffer.text); $("sheffer-status").textContent='Система скопирована.';}
  catch {$("sheffer-status").textContent='Выделите формулы и скопируйте через Ctrl+C.';}
});
