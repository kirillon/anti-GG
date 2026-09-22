// Optional end-to-end test. Requires Node >=22 and Chromium; no npm dependencies.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp, readFile, readdir, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import net from 'node:net';

const sleep = ms => new Promise(r => setTimeout(r, ms));
const profile = await mkdtemp(join(tmpdir(), 'veitch-browser-'));
const artifacts = resolve('artifacts');
await mkdir(artifacts, {recursive:true});
const downloads = join(profile, 'downloads');
await mkdir(downloads);
const reservation = net.createServer();
await new Promise(r => reservation.listen(0, '127.0.0.1', r));
const port = reservation.address().port;
await new Promise(r => reservation.close(r));
const app = spawn(process.env.PYTHON || '.venv/bin/python', ['app.py', '--port', String(port)], {stdio:'ignore'});
const chrome = spawn(process.env.CHROMIUM || 'chromium', [
  '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
  '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'
], {stdio:'ignore'});
let ws;
try {
  let debug;
  for (let i=0; i<100; i++) {
    try {debug = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n'); break;} catch {await sleep(100);}
  }
  assert.ok(debug, 'Chromium failed to start');
  for (let i=0; i<100; i++) {
    try {if ((await fetch(`http://127.0.0.1:${port}/api/status`)).ok) break;} catch {}
    await sleep(100);
  }
  ws = new WebSocket(`ws://127.0.0.1:${debug[0]}${debug[1]}`);
  await new Promise((r, j) => {ws.onopen=r; ws.onerror=j;});
  let sequence = 0;
  const pending = new Map();
  const errors = [];
  ws.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
    if (pending.has(message.id)) {
      const {resolve, reject, timeout} = pending.get(message.id);
      clearTimeout(timeout); pending.delete(message.id);
      if (message.error) reject(new Error(JSON.stringify(message.error))); else resolve(message.result);
    }
  };
  function command(method, params={}, sessionId) {
    return new Promise((resolve, reject) => {
      const id = ++sequence;
      const timeout = setTimeout(() => {pending.delete(id); reject(new Error(`Timeout: ${method}`));}, 15000);
      pending.set(id, {resolve, reject, timeout});
      ws.send(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}));
    });
  }
  const {targetId} = await command('Target.createTarget', {url:'about:blank'});
  const {sessionId} = await command('Target.attachToTarget', {targetId, flatten:true});
  const call = (method, params) => command(method, params, sessionId);
  const evaluate = async expression => {
    const response = await call('Runtime.evaluate', {expression, returnByValue:true, awaitPromise:true});
    assert.equal(response.exceptionDetails, undefined, JSON.stringify(response.exceptionDetails));
    return response.result.value;
  };
  const waitFor = async expression => {
    for (let i=0; i<100; i++) {if (await evaluate(expression)) return; await sleep(100);}
    throw new Error(`Condition timed out: ${expression}`);
  };
  await call('Runtime.enable');
  await call('Page.enable');
  await call('Emulation.setDeviceMetricsOverride', {width:1440,height:1200,deviceScaleFactor:1,mobile:false});
  await command('Browser.setDownloadBehavior', {behavior:'allow', downloadPath:downloads});
  await call('Page.navigate', {url:`http://127.0.0.1:${port}/`});
  await waitFor(`document.querySelectorAll('[data-group]').length === 4`);
  assert.match(await evaluate(`document.getElementById('diagram').textContent`), /C · D/);
  assert.match(await evaluate(`document.getElementById('model-status').textContent`), /подключена/);
  let shot = await call('Page.captureScreenshot', {format:'png', captureBeyondViewport:true});
  await writeFile(join(artifacts, 'browser-desktop.png'), Buffer.from(shot.data, 'base64'));
  await evaluate(`document.getElementById('svg-download').click(); document.getElementById('png-download').click()`);
  for (let i=0; i<100; i++) {
    const files = await readdir(downloads);
    if (files.includes('veitch.svg') && files.includes('veitch.png')) break;
    await sleep(100);
  }
  assert.match(await readFile(join(downloads, 'veitch.svg'), 'utf8'), /Минимальная ДНФ/);
  const png = await readFile(join(downloads, 'veitch.png'));
  assert.equal(png.subarray(1,4).toString(), 'PNG');
  await writeFile(join(artifacts, 'example.png'), png);
  await writeFile(join(artifacts, 'example.svg'), await readFile(join(downloads, 'veitch.svg')));
  await evaluate(`document.querySelector('[data-example]').click()`);
  await waitFor(`document.getElementById('diagram').textContent.includes('F = A') && document.querySelectorAll('[data-group]').length === 1`);
  await evaluate(`document.getElementById('function').value='A+'; document.getElementById('function').dispatchEvent(new Event('input'));`);
  assert.equal(await evaluate(`document.getElementById('result').hidden`), true);
  await evaluate(`document.getElementById('form').requestSubmit()`);
  await waitFor(`!document.getElementById('error').hidden`);
  assert.equal(await evaluate(`document.getElementById('result').hidden`), true);
  await evaluate(`document.querySelectorAll('[data-example]')[1].click()`);
  await waitFor(`!document.getElementById('result').hidden`);
  await call('Emulation.setDeviceMetricsOverride', {width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert.equal(await evaluate(`document.documentElement.scrollWidth <= window.innerWidth`), true);
  shot = await call('Page.captureScreenshot', {format:'png', captureBeyondViewport:true});
  await writeFile(join(artifacts, 'browser-mobile.png'), Buffer.from(shot.data, 'base64'));
  await evaluate(`document.getElementById('system-tab').click()`);
  assert.equal(await evaluate(`document.getElementById('single-section').hidden`), true);
  await evaluate(`document.getElementById('add-function').click()`);
  assert.equal(await evaluate(`document.querySelectorAll('#system-inputs input').length`), 4);
  await evaluate(`document.querySelector('#system-inputs .function-row:last-child button').click()`);
  await evaluate(`document.getElementById('system-form').requestSubmit()`);
  await waitFor(`!document.getElementById('system-result').hidden`);
  assert.match(await evaluate(`document.getElementById('system-cost').textContent`), /13/);
  assert.equal(await evaluate(`document.querySelectorAll('#system-product-maps svg').length`), 7);
  assert.equal(await evaluate(`document.querySelectorAll('#system-output-maps svg').length`), 3);
  assert.equal(await evaluate(`document.querySelectorAll('#system-matrix tr').length`), 14);
  assert.equal(await evaluate(`document.documentElement.scrollWidth <= window.innerWidth`), true);
  await command('Browser.grantPermissions', {origin:`http://127.0.0.1:${port}`, permissions:['clipboardReadWrite','clipboardSanitizedWrite']});
  await evaluate(`document.getElementById('copy-matrix').click()`);
  await waitFor(`document.getElementById('copy-status').textContent.includes('скопирована')`);
  const copied = await evaluate(`(async () => {const items=await navigator.clipboard.read(); return await (await items[0].getType('text/html')).text();})()`);
  assert.match(copied, /<table/);
  assert.match(copied, /Импликанта/);
  assert.match(copied, /colspan/);
  assert.match(copied, /overline/);
  assert.equal(await evaluate(`document.querySelectorAll('#sheffer-outputs p').length`),3);
  await evaluate(`document.getElementById('copy-sheffer').click()`);
  await waitFor(`document.getElementById('sheffer-status').textContent.includes('скопирована')`);
  const fullFormulas = await evaluate(`navigator.clipboard.readText()`);
  assert.match(fullFormulas, /NAND\(/);
  assert.doesNotMatch(fullFormulas, /\bT\d+\b/);
  assert.doesNotMatch(await evaluate(`document.getElementById('sheffer-outputs').textContent`), /\bT\d+\b/);
  assert.equal(await evaluate(`document.querySelectorAll('#sheffer-diagram [data-output]').length`), 3);
  assert.equal(await evaluate(`document.querySelectorAll('#sheffer-diagram [data-gate]').length === systemResult.sheffer.gates.length`), true);
  assert.equal(await evaluate(`document.documentElement.scrollWidth <= window.innerWidth`), true);
  await evaluate(`document.getElementById('sheffer-zoom').value='50'; document.getElementById('sheffer-zoom').dispatchEvent(new Event('input'))`);
  assert.equal(await evaluate(`document.querySelector('#sheffer-diagram svg').style.width === (document.querySelector('#sheffer-diagram svg').viewBox.baseVal.width / 2) + 'px'`), true);
  await evaluate(`document.getElementById('sheffer-svg').click(); document.getElementById('sheffer-png').click()`);
  for (let i=0; i<100; i++) {
    const files = await readdir(downloads);
    if (files.includes('sheffer-system.svg') && files.includes('sheffer-system.png')) break;
    await sleep(100);
  }
  assert.match(await readFile(join(downloads, 'sheffer-system.svg'), 'utf8'), /data-output="F3"/);
  const circuitPng = await readFile(join(downloads, 'sheffer-system.png'));
  assert.equal(circuitPng.subarray(1,4).toString(), 'PNG');
  await writeFile(join(artifacts, 'sheffer-system.png'), circuitPng);
  await writeFile(join(artifacts, 'sheffer-system.svg'), await readFile(join(downloads, 'sheffer-system.svg')));
  await evaluate(`document.getElementById('download-matrix').click()`);
  for (let i=0; i<100; i++) {
    if ((await readdir(downloads)).includes('implicant-matrix.html')) break;
    await sleep(100);
  }
  assert.match(await readFile(join(downloads, 'implicant-matrix.html'), 'utf8'), /<table/);
  await call('Emulation.setDeviceMetricsOverride', {width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  shot = await call('Page.captureScreenshot', {format:'png', captureBeyondViewport:false});
  await writeFile(join(artifacts, 'browser-system.png'), Buffer.from(shot.data, 'base64'));
  for (const [id,file] of [['system-matrix','browser-matrix.png'],['system-output-maps','browser-maps.png'],['sheffer-section','browser-sheffer.png']]) {
    await evaluate(`document.getElementById('${id}').scrollIntoView()`);
    shot = await call('Page.captureScreenshot', {format:'png', captureBeyondViewport:false});
    await writeFile(join(artifacts,file),Buffer.from(shot.data,'base64'));
  }

  await evaluate(`document.getElementById('variable-count').value='3';
    [...document.querySelectorAll('#system-inputs input')].forEach((input,i) => {input.value=['2','','0,1,2,3,4,5,6,7'][i]; input.dispatchEvent(new Event('input'));});
    document.getElementById('system-form').requestSubmit()`);
  await waitFor(`!document.getElementById('system-result').hidden`);
  assert.equal(await evaluate(`(() => {const inner=document.querySelector('#sheffer-outputs .sheffer-not .sheffer-not'); return inner && inner.getBoundingClientRect().top > inner.parentElement.getBoundingClientRect().top;})()`), true);
  assert.equal(await evaluate(`document.querySelectorAll('#sheffer-diagram [data-output]').length`), 3);
  await evaluate(`document.getElementById('variable-count').value='2';
    [...document.querySelectorAll('#system-inputs input')].forEach(input => {input.value='2,3'; input.dispatchEvent(new Event('input'));});
    document.getElementById('system-form').requestSubmit()`);
  await waitFor(`!document.getElementById('system-result').hidden`);
  assert.equal(await evaluate(`document.querySelectorAll('#sheffer-diagram [data-gate]').length`), 0);
  assert.equal(await evaluate(`document.querySelectorAll('#sheffer-diagram [data-output]').length`), 3);
  assert.equal(await evaluate(`document.querySelector('#sheffer-diagram svg').viewBox.baseVal.width >= 700`), true);
  await evaluate(`document.querySelector('#system-inputs input').value='16'; document.querySelector('#system-inputs input').dispatchEvent(new Event('input')); document.getElementById('system-form').requestSubmit()`);
  await waitFor(`!document.getElementById('system-error').hidden`);
  assert.equal(await evaluate(`document.getElementById('system-result').hidden`), true);
  assert.deepEqual(errors, []);
  console.log('PASS: single function and system UI, labels, matrix HTML clipboard/download, validation, SVG/PNG, mobile layout');
} finally {
  ws?.close();
  const stop = async child => {
    if (child.exitCode !== null) return;
    const exited = new Promise(r => child.once('exit', r)); child.kill();
    await Promise.race([exited, sleep(3000)]);
    if (child.exitCode === null) {child.kill('SIGKILL'); await exited;}
  };
  await stop(chrome); await stop(app);
  await rm(profile, {recursive:true,force:true,maxRetries:5,retryDelay:200});
}
