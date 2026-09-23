// Formula-driven XLSX export, using the installed artifact runtime (no browser required).
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const modules = process.env.VEITCH_NODE_MODULES || path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const require = createRequire(path.join(modules,'veitch-loader.cjs'));
const {Workbook,SpreadsheetFile} = await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const [input, output, preview] = process.argv.slice(2);
const data = JSON.parse(await fs.readFile(input,'utf8'));
const wb = Workbook.create();
const wave = wb.worksheets.add('Диаграмма');
const calc = wb.worksheets.add('Расчёт');
function col(i) {let name=''; for (i++;i;i=Math.floor((i-1)/26)) name=String.fromCharCode(65+(i-1)%26)+name;return name;}
const last=col(data.steps+1), waveLast=col(data.steps), rows={};
data.signals.forEach((name,i) => rows[name]=i+7);
calc.getRange('A1').values=[['Расчёт временной диаграммы']];
calc.getRange('A2:B4').values=[['Период входного набора',data.period],['Переход 0 → 1 (t01)',data.t01],['Переход 1 → 0 (t10)',data.t10]];
calc.getRange('D2').values=[['Время и задержки — дискретные такты; транспортная модель.']];
calc.getRange('D3').values=[['До t=0 схема установилась при нулевых входах. Последний набор удерживается.']];
calc.getRange('D4').values=[['Изменяйте жёлтые B2:B4; длина записи фиксирована при экспорте.']];
calc.getRange('A6:B6').values=[['Сигнал','t < 0']];
calc.getRange(`C6:${last}6`).values=[Array.from({length:data.steps},(_,i)=>i)];
calc.getRange('B2:B4').format.fill='#fff2cc';
calc.dataValidations.add({range:'B2',rule:{type:'whole',operator:'between',formula1:1,formula2:32}});
calc.dataValidations.add({range:'B3:B4',rule:{type:'whole',operator:'between',formula1:0,formula2:8}});
for(const name of data.circuit.variables) {
  const r=rows[name], bit=data.circuit.variables.length-1-data.circuit.variables.indexOf(name);
  calc.getRange(`A${r}:B${r}`).values=[[name,0]];
  calc.getRange(`C${r}:${last}${r}`).formulas=[Array.from({length:data.steps},(_,t)=>`=MOD(INT(MIN(INT(${col(t+2)}$6/$B$2),${2**data.circuit.variables.length-1})/${2**bit}),2)`)];
}
for(const gate of data.circuit.gates) {
  const r=rows[gate.name];
  calc.getRange(`A${r}`).values=[[`${gate.name} (${gate.kind}: ${gate.inputs.join(', ')})`]];
  calc.getRange(`B${r}`).formulas=[[`=1-PRODUCT(${gate.inputs.map(s=>`B${rows[s]}`).join(',')})`]];
  calc.getRange(`C${r}:${last}${r}`).formulas=[Array.from({length:data.steps},(_,t)=>{
    const time=`${col(t+2)}$6`;
    const ideal=(delay,previous=0)=>`IF(${time}-${delay}-${previous}<0,$B${r},1-PRODUCT(${gate.inputs.map(s=>`INDEX($C${rows[s]}:$${last}${rows[s]},1,MAX(1,${time}-${delay}-${previous}+1))`).join(',')}))`;
    const rise=`AND(${time}>=$B$3,${ideal('$B$3')}=1,${ideal('$B$3',1)}=0)`;
    const fall=`AND(${time}>=$B$4,${ideal('$B$4')}=0,${ideal('$B$4',1)}=1)`;
    const prior=`${col(t+1)}${r}`;
    return `=IF($B$3<=$B$4,IF(${rise},1,IF(${fall},0,${prior})),IF(${fall},0,IF(${rise},1,${prior})))`;

  })];
}
for(const o of data.circuit.outputs) {
  const r=rows[o.name]; calc.getRange(`A${r}`).values=[[o.name]];
  calc.getRange(`B${r}:${last}${r}`).formulas=[Array.from({length:data.steps+1},(_,t)=>`=${col(t+1)}${rows[o.expression]}`)];
}
const endRow=6+data.signals.length;
calc.getRange(`A1:${last}${endRow}`).format.font={name:'Arial',size:10};
calc.getRange(`A7:B${endRow}`).format.columnWidth=25;
calc.getRange(`C6:${last}${endRow}`).format.columnWidth=4;
calc.getRange(`A6:${last}6`).format.fill='#e7e7e7';
calc.freezePanes.freezeRows(6); calc.freezePanes.freezeColumns(2);
calc.getRange(`B6:${last}${endRow}`).setNumberFormat('0');
wave.showGridLines=false;
wave.getRange('A1').values=[['Временная диаграмма']];
wave.getRange(`B1:${waveLast}1`).merge();
wave.getRange('B1').values=[['1 — жёлтый; 0 — нижняя линия. Параметры — на листе «Расчёт».']];
wave.getRange('A2').values=[['Время, интервалы']];
wave.getRange('A3').values=[[`1 интервал = ${data.period} тактов`]];
for(let t=0;t<data.steps;t+=data.period) {
  const range=wave.getRange(`${col(t+1)}2:${col(Math.min(t+data.period,data.steps))}2`);
  range.merge();range.values=[[t/data.period]];range.format.horizontalAlignment='center';
}
for(const [i,name] of data.signals.entries()) {
  const r=4+i*3;
  wave.getRange(`A${r}`).values=[[name]];
  const range=wave.getRange(`B${r}:${waveLast}${r}`);
  range.formulas=[Array.from({length:data.steps},(_,t)=>`='Расчёт'!${col(t+2)}${rows[name]}`)];
  range.setNumberFormat(';;;');
  range.format.borders={bottom:{style:'thin',color:'#333333'}};
  range.conditionalFormats.add('cellIs',{operator:'equal',formula:1,format:{fill:'#ffc000',border:{top:{style:'medium',color:'#111111'}}}});
  range.conditionalFormats.add('cellIs',{operator:'equal',formula:0,format:{border:{bottom:{style:'medium',color:'#111111'}}}});
  if(data.steps>1) wave.getRange(`C${r}:${waveLast}${r}`).conditionalFormats.addCustom(`C${r}<>B${r}`,{border:{left:{style:'thin',color:'#111111'}}});
}
const bottom=4+(data.signals.length-1)*3;
wave.getRange(`A1:${waveLast}${bottom}`).format.font={name:'Arial',size:11};
wave.getRange(`A1:A${bottom}`).format.columnWidthPx=185;
wave.getRange(`B2:${waveLast}${bottom}`).format.columnWidthPx=7;
wave.getRange(`A2:${waveLast}${bottom}`).format.rowHeightPx=13;
wave.getRange(`A2:${waveLast}2`).format.rowHeightPx=24;
for(let i=0;i<data.signals.length;i++) wave.getRange(`A${4+i*3}:${waveLast}${4+i*3}`).format.rowHeightPx=20;
for(let t=0;t<data.steps;t+=data.period) wave.getRange(`${col(t+1)}2:${col(t+1)}${bottom}`).format.borders={left:{style:'thin',color:'#888888'}};
wave.freezePanes.freezeColumns(1);wave.freezePanes.freezeRows(2);
calc.getRange(`A${endRow+3}`).values=[['Образец оформления']];
calc.getRange(`B${endRow+3}`).values=[['https://docs.google.com/spreadsheets/d/1Mibex8P9y2NQ81ddJaRMKkg0H5U2j2xO/edit']];
// Validate every gate against the independent Python simulation before delivering the file.
for(const name of data.signals) {
  const actual=calc.getRange(`C${rows[name]}:${last}${rows[name]}`).values[0];
  if(actual.some((v,i)=>v!==data.values[name][i])) throw new Error(`Excel calculation mismatch: ${name}`);
}
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!',options:{useRegex:true,maxResults:10},maxChars:1200});
console.log(errors.ndjson);
await fs.mkdir(path.dirname(output),{recursive:true});
await (await SpreadsheetFile.exportXlsx(wb)).save(output);
if(preview) {
  for(const [sheetName,range,file] of [['Диаграмма',`A1:${waveLast}${bottom}`,preview],['Расчёт','A1:R18',preview.replace(/\.png$/, '-calc.png')]]) {
    const blob=await wb.render({sheetName,range,scale:1});
    await fs.writeFile(file,new Uint8Array(await blob.arrayBuffer()));
  }
}
