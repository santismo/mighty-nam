/* Node 20+; no device/audio/network access. MIT © 2026 santismo. */
'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const core = require('../docs/builder/core.js');
const recipeDir=({looper:'looper-builder',v28:'builder-v28',v23:'builder'})[process.env.MIGHTY_NAM_RECIPE]||'builder';
require('../docs/'+recipeDir+'/recipe.js');
const recipe = globalThis.MightyNamRecipe;
const extended = ['NAMLNK27','NAMLNK28','NAMLNK29'].includes(recipe.identity);
const copy = () => structuredClone(recipe);
const stockPath = process.env.MIGHTY_NAM_STOCK_FILE;
const stock = stockPath ? new Uint8Array(fs.readFileSync(stockPath)) : null;

test('release contains original code, hooks, licensed starters and global erase', () => {
  assert.equal(recipe.operations.length, extended?21:17);
  assert.equal(recipe.operations.filter(x => x.kind === 'code').length, extended?6:4);
  assert.equal(recipe.operations.filter(x => x.kind === 'hook').length, extended?13:11);
  assert.equal(recipe.operations.filter(x => x.kind === 'fill').length, 1);
  assert.equal(recipe.presets, recipe.identity==='NAMLNK29'?'riffsmith-mit-7':'riffsmith-mit-3'); assert.equal(recipe.captures_included, true); assert.equal(recipe.operations.filter(x => x.kind === 'preset-bank').length, 1);
  assert.ok(!JSON.stringify(recipe).includes('original":'));
  assert.ok(recipe.operations.every(x => !('original' in x)));
  assert.equal(recipe.operations.reduce((n,x) => n + (['fill','preset-bank'].includes(x.kind) ? 0 : x.length), 0), recipe.identity==='NAMLNK29'?40420:recipe.identity==='NAMLNK28'?38012:recipe.identity==='NAMLNK27'?36128:25556);
});
test('wrong size and renamed/corrupted stock fail before building', async () => {
  await assert.rejects(core.inspect(new Uint8Array(100)), /Unsupported file size/);
  await assert.rejects(core.inspect(new Uint8Array(core.inputBytes)), /Unsupported firmware/);
});
test('WebCrypto is required and no network/device/audio facilities exist', async () => {
  const source = fs.readFileSync(path.join(root,'docs/builder/core.js'),'utf8');
  const scope = {Uint8Array}; vm.createContext(scope); vm.runInContext(source, scope);
  await assert.rejects(scope.MightyNamBuilder.sha(new Uint8Array(1)), /needs HTTPS/);
  for (const file of ['core.js','ui.js']) {
    const text = fs.readFileSync(path.join(root,'docs/builder',file),'utf8');
    assert.ok(!/\b(fetch|XMLHttpRequest|WebSocket|AudioContext|getUserMedia|sendBeacon)\s*\(/.test(text));
    assert.ok(!/navigator\.(bluetooth|usb|hid|serial|mediaDevices)/.test(text));
  }
  const html = fs.readFileSync(path.join(root,'docs/builder.html'),'utf8');
  assert.ok(html.includes("connect-src 'none'")); assert.ok(html.includes("form-action 'none'"));
});
test('recipe and checked-in provenance match', async () => {
  const audit = JSON.parse(fs.readFileSync(path.join(root,'docs',recipeDir,'provenance.json')));
  assert.equal(await core.sha(new Uint8Array(fs.readFileSync(path.join(root,'docs',recipeDir,'recipe.js')))), audit.recipe_sha256);
  assert.equal(recipe.output.sha256, audit.output_sha256);
  assert.equal(recipe.elf_sha256, audit.elf_sha256);
});
test('exact local stock produces the independently staged image, without editing the input', {skip:!stock}, async () => {
  const before = await core.sha(stock);
  const built = await core.build(stock, recipe);
  assert.equal(await core.sha(stock), before);
  assert.equal(await core.sha(built.bytes), recipe.identity==='NAMLNK29'?'3448b14cb56d31c5a58ae89c7d4ea3df4ef704779efd95a2a7d858edb223d778':recipe.identity==='NAMLNK28'?'8d2e103361ace00ee12e4e32ee41427b4d06136d7214aa375d5a4a6b7c807f77':recipe.identity==='NAMLNK27'?'ccb1a2c1836ccc5045a6d53544add2ed46b4055ad4ec9df74a6feaa64368f42a':'de1da69e63cf6457f0fae7631655fe62c49d37aa7435b5326107c0a0e8521698');
  assert.equal(built.report.presets,recipe.presets); assert.equal(built.report.flashed,false);
  assert.equal(built.report.hardware_verified,false);
  for(const license of Object.values(built.report.license_notices)) assert.match(license,/Permission is hereby granted/);
  assert.match(built.report.license_notices['RiffSmith captures'],/Matt Hartman/);
  const again = await core.build(stock, recipe); assert.deepEqual(again.bytes,built.bytes);
  // All container headers, setup, text and non-payload data must stay exact.
  const dv = new DataView(stock.buffer,stock.byteOffset,stock.byteLength);
  const start = dv.getUint32(0x224+12+8,true), size = dv.getUint32(0x224+12+4,true);
  assert.deepEqual(built.bytes.subarray(0,start+540),stock.subarray(0,start+540));
  assert.deepEqual(built.bytes.subarray(start+size),stock.subarray(start+size));
  const payload = new Uint8Array(14229504);
  for (let i=0;i<payload.length/512;i++) {
    const at=start+(i+1)*540;
    assert.deepEqual(built.bytes.subarray(at,at+28),stock.subarray(at,at+28));
    payload.set(built.bytes.subarray(at+28,at+540),i*512);
    for (let j=0;j<512;j++) if (built.bytes[at+28+j]!==stock[at+28+j])
      assert.ok(recipe.operations.some(op => i*512+j>=op.offset && i*512+j<op.offset+op.length));
  }
  const count=recipe.identity==='NAMLNK29'?7:3;
  assert.ok(payload.subarray(0x344000+count*16384,0x360000).every(x=>x===255));
  assert.equal(recipe.starter_presets.length,count);
  for(let i=0;i<count;i++) assert.equal(new DataView(payload.buffer).getUint32(0x344000+i*16384,true),0x3142504e);
  assert.ok(payload.subarray(0x364000,0x366000).every(x=>x===255));
});
test('same-length corrupt stock is rejected', {skip:!stock}, async () => {
  const bad=stock.slice();bad[100000]^=1;
  await assert.rejects(core.build(bad,recipe), /Unsupported firmware/);
});
const mutations = [
  ['wrong product',r=>r.target='OTHER',/Unsupported builder/],
  ['wrong input version',r=>r.input.sha256='0'.repeat(64),/Recipe input/],
  ['unapproved bank',r=>r.presets='private',/licensed starter bank/],
  ['missing operation',r=>r.operations.pop(),/Incomplete/],
  ['overlap',r=>{r.operations[2].offset=r.operations[1].offset},/overlap/],
  ['out of bounds',r=>{r.operations[0].offset=-1},/out of bounds/],
  ['code escape',r=>{r.operations[0].offset=0},/audited region/],
  ['unknown hook',r=>{r.operations.find(x=>x.kind==='hook').offset=0x1000},/Unknown hook/],
  ['changed code',r=>{r.operations[0].data='AAAA'+r.operations[0].data.slice(4)},/checksum mismatch/],
  ['patch-site mismatch',r=>{r.operations[0].before_sha256='0'.repeat(64)},/Patch-site/],
  ['changed starter payload',r=>{r.operations.find(x=>x.kind==='preset-bank').data='AAAA'+r.operations.find(x=>x.kind==='preset-bank').data.slice(4)},/bank checksum/]
  ,['filled global payload',r=>{r.operations.find(x=>x.kind==='fill').value=0},/storage operation/],
  ['output checksum mismatch',r=>{r.output.sha256='0'.repeat(64)},/firmware failed/],
  ['output payload mismatch',r=>{r.output.payload_sha256='0'.repeat(64)},/payload failed/],
];
for (const [name,mutate,error] of mutations) test('rejects '+name,{skip:!stock},async()=>{
  const r=copy();mutate(r);await assert.rejects(core.build(stock,r),error);
});

for (const [label,variable] of [['ChopTones V3.0.5','MIGHTY_NAM_CT_FILE'],['legacy V1.5.6','MIGHTY_NAM_LEGACY_FILE']]) {
  const file=process.env[variable];
  test('rejects actual '+label+' stock file',{skip:!file},async()=>{
    const data=new Uint8Array(fs.readFileSync(file));
    await assert.rejects(core.build(data,recipe),/Unsupported file size|Unsupported firmware/);
  });
}
test('output matches independent staged file byte for byte',{skip:!stock||!process.env.MIGHTY_NAM_STAGED_FILE},async()=>{
  const result=await core.build(stock,recipe);
  assert.deepEqual(result.bytes,new Uint8Array(fs.readFileSync(process.env.MIGHTY_NAM_STAGED_FILE)));
});

test('licensed starter layout rejects a recomputed outer checksum', {skip:!stock}, async()=>{
 const r=copy(),op=r.operations.find(x=>x.kind==='preset-bank');
 const data=Uint8Array.from(Buffer.from(op.data,'base64'));data[32]^=1;
 op.data=Buffer.from(data).toString('base64');op.sha256=await core.sha(data);r.starter_bank_sha256=op.sha256;
 await assert.rejects(core.build(stock,r),/starter commit/);
});

for(const slot of [3,4,5,6])test('rejects a damaged default color '+(slot+1)+' even with a recomputed bank checksum',{skip:!stock||recipe.identity!=='NAMLNK29'},async()=>{
 const r=copy(),op=r.operations.find(x=>x.kind==='preset-bank');
 const data=Uint8Array.from(Buffer.from(op.data,'base64'));data[slot*16384+32]^=1;
 op.data=Buffer.from(data).toString('base64');op.sha256=await core.sha(data);r.starter_bank_sha256=op.sha256;
 await assert.rejects(core.build(stock,r),/starter commit/);
});
