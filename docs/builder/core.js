/* mighty-nam local builder. MIT © 2026 santismo. No network or device APIs. */
(function (root) {
  'use strict';
  const INPUT_SHA = '39fa7057865f95e4c52c48544cd8284f4da606d3ac29e985e9b8938a3237467e';
  const PAYLOAD_SHA = 'e971240a1e333003804cfd154e5ee053026254bbf09b11499e8b4968d3600752';
  const INPUT_BYTES = 15009655, PAYLOAD_BYTES = 14229504;
  const BANK_START = 0x344000, BANK_END = 0x360000;
  const GLOBAL_START = 0x364000, GLOBAL_END = 0x366000;
  const HOOKS = new Map([[0x55b4,8],[0x581a,10],[0xe19c,8],[0x5868,8],
    [0x6a38,8],[0x1088c,8],[0x21243,4],[0x6498,4],[0x229b0,4],[0x8c96,4],[0xb23c,8]]);
  const CODE = new Map([['.text',[0x1c45c,0x1d830]],['.retired_audio',[0x1c0e8,0x1c270]],
    ['.ARM.exidx',[0x1c0e8,0x1c270]],['.banktext',[0x366000,0x36b000]]]);
  function need(ok, message) { if (!ok) throw new Error(message); }
  function bytes(value) {
    need(value instanceof Uint8Array, 'Expected a firmware byte array.');
    return value;
  }
  async function sha(value) {
    need(root.crypto && root.crypto.subtle, 'This browser needs HTTPS or the downloaded offline builder.');
    const digest = await root.crypto.subtle.digest('SHA-256', bytes(value));
    return Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2, '0')).join('');
  }
  function ascii(data, start, length) {
    return String.fromCharCode(...data.subarray(start, start + length));
  }
  function equal(a, b) { return a.length === b.length && a.every((x, i) => x === b[i]); }
  function parse(data) {
    const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
    need(data.length === INPUT_BYTES && ascii(data, 0, 7) === 'NUX DFU' && data[7] === 2,
      'Unsupported NUX firmware container.');
    need(view.getUint32(8, true) === data.length, 'Firmware length is invalid.');
    need(ascii(data, 20, 256).split('\0')[0] === 'MIGHTY PLUG PRO DFU', 'This is not Mighty Plug Pro firmware.');
    const sections = ['TEXT','BINA','EXTR'].map((tag, i) => {
      const pos = 0x224 + 12 * i;
      need(ascii(data, pos, 4) === tag, 'Firmware directory is invalid.');
      const length = view.getUint32(pos + 4, true), offset = view.getUint32(pos + 8, true);
      need(offset >= 956 && length > 0 && offset + length <= data.length, 'Firmware section is out of bounds.');
      return { offset, length };
    });
    const ordered = sections.slice().sort((a,b) => a.offset - b.offset);
    need(ordered.every((s,i) => !i || ordered[i-1].offset+ordered[i-1].length <= s.offset), 'Firmware sections overlap.');
    need(sections[2].length === 256 && data.subarray(sections[2].offset, sections[2].offset+256).every(x=>x===0), 'Unsupported EXTR section.');
    const bina = sections[1], setup = bina.offset;
    need(bina.length % 540 === 0 && bina.length / 540 === PAYLOAD_BYTES / 512 + 1, 'Invalid page count.');
    need(data[setup+2] === 0 && data[setup+3] === 1, 'Invalid setup record.');
    const identity = data.slice(setup+28, setup+44).map(x => x ^ 255);
    need(ascii(identity, 0, 16) === 'PLUGXDFU20240812', 'Unrecognized update identity.');
    need(view.getUint32(setup+52, false) === PAYLOAD_BYTES, 'Invalid payload length.');
    const payload = new Uint8Array(PAYLOAD_BYTES), count = PAYLOAD_BYTES / 512;
    for (let i = 0; i < count; i++) {
      const at = setup + (i+1)*540;
      need(data[at+2] === 0 && data[at+3] === 4, 'Invalid page opcode.');
      need(view.getUint32(at+12, false) === (i === count-1 ? 0xffffffff : i), 'Invalid page order.');
      payload.set(data.subarray(at+28, at+540), i*512);
    }
    return { payload, bina };
  }
  async function inspect(input) {
    bytes(input);
    need(input.length === INPUT_BYTES, 'Unsupported file size. Select the extracted MP3_OR_V3.0.5.bin, not the ZIP, updater, or ChopTones firmware.');
    const digest = await sha(input);
    need(digest === INPUT_SHA, 'Unsupported firmware (SHA-256 ' + digest + '). Only the exact V3.0.5 Original file is supported. Do not rename a newer file to bypass this check.');
    const parsed = parse(input);
    need(await sha(parsed.payload) === PAYLOAD_SHA, 'Stock payload checksum mismatch.');
    return { sha256: digest, bytes: input.length, version: 'V3.0.5 Original' };
  }
  function decode(base64, maxLength = 40000) {
    need(typeof base64 === 'string' && base64.length <= maxLength && /^[A-Za-z0-9+/]*={0,2}$/.test(base64), 'Invalid builder payload.');
    const raw = root.atob(base64);
    return Uint8Array.from(raw, c => c.charCodeAt(0));
  }
  function crc(data) {
    let c=0xffffffff;
    for(const b of data) { c^=b; for(let i=0;i<8;i++) c=(c&1)?(c>>>1)^0xedb88320:c>>>1; }
    return (c^0xffffffff)>>>0;
  }
  async function validateStarters(bank, recipe) {
    need(bank.length === BANK_END-BANK_START && await sha(bank) === recipe.starter_bank_sha256, 'Starter bank checksum mismatch.');
    need(bank.subarray(49152).every(x=>x===255), 'Unexpected extra starter presets.');
    for(let i=0;i<3;i++) {
      const record=bank.subarray(i*16384,i*16384+8192), d=new DataView(record.buffer,record.byteOffset,8192);
      const row=recipe.starter_presets[i];
      need(d.getUint32(0,true)===0x3142504e && d.getUint32(4,true)===1 && d.getUint32(8,true)===i && d.getUint32(12,true)===1 && d.getUint32(20,true)===1 && d.getUint32(24,true)===8 && d.getUint32(28,true)===0, 'Invalid starter header.');
      need(d.getUint32(8184,true)===crc(record.subarray(0,8184)) && d.getUint32(8188,true)===0x454e4f44, 'Invalid starter commit.');
      const model=new Uint8Array(8192).fill(255); model.set(record.subarray(256,7772));
      const m=new DataView(model.buffer);
      need([0x3241504d,1,48000,1871,7484,crc(model.subarray(32,7516)),1,0].every((v,j)=>m.getUint32(j*4,true)===v), 'Invalid A2 Lite starter model.');
      for(let n=32;n<7516;n+=4) need(Number.isFinite(m.getFloat32(n,true)), 'Nonfinite starter weight.');
      const digest=await sha(model);
      need(row.color===i && row.model_sha256===digest && d.getUint32(16,true)===crc(model) && Array.from(record.subarray(32,64),x=>x.toString(16).padStart(2,'0')).join('')===digest, 'Starter capture mismatch.');
      need(equal(record.subarray(128,256),Uint8Array.from(row.effects)) && equal(record.subarray(7812,7844),Uint8Array.from(row.extra_fx)) && d.getUint32(7808,true)===0x33315846, 'Starter settings mismatch.');
      need(record.subarray(7772,7808).every(x=>x===255) && record.subarray(7844,8184).every(x=>x===255) && bank.subarray(i*16384+8192,(i+1)*16384).every(x=>x===255), 'Unexpected starter padding.');
    }
  }
  async function build(input, recipe) {
    // Snapshot both inputs before any asynchronous work; never edit the user's file.
    const original = bytes(input).slice(), r = JSON.parse(JSON.stringify(recipe));
    await inspect(original);
    need(r.schema === 'mighty-nam-local-builder-1' && r.identity === 'NAMLNK23' && r.target === 'NUX-MP3', 'Unsupported builder recipe.');
    need(r.input.sha256 === INPUT_SHA && r.input.bytes === INPUT_BYTES && r.input.payload_sha256 === PAYLOAD_SHA, 'Recipe input does not match this builder.');
    need(r.presets === 'riffsmith-mit-3' && r.captures_included === true && r.starter_presets?.length === 3, 'Only the licensed starter bank is allowed.');
    need(r.output.name === 'mighty-nam-NAMLNK23-r2-experimental.bin' && /^[a-f0-9]{64}$/.test(r.output.sha256), 'Invalid output specification.');
    need(Array.isArray(r.operations) && r.operations.length === CODE.size + HOOKS.size + 2, 'Incomplete builder recipe.');
    const parsed = parse(original), payload = parsed.payload.slice();
    const spans = [], seen = new Set();
    for (const op of r.operations) {
      const { offset, length } = op;
      need(Number.isSafeInteger(offset) && Number.isSafeInteger(length) && offset >= 0 && length > 0 && offset+length <= payload.length, 'Patch is out of bounds.');
      need(!spans.some(([a,b]) => offset < b && offset+length > a), 'Patches overlap.');
      need(!seen.has(op.id), 'Duplicate patch.'); seen.add(op.id);
      let replacement;
      if (op.kind === 'code') {
        const range = CODE.get(op.id);
        need(range && offset >= range[0] && offset+length <= range[1], 'Code outside its audited region.');
        replacement = decode(op.data);
      } else if (op.kind === 'hook') {
        need(HOOKS.get(offset) === length && op.id === 'hook-' + offset.toString(16), 'Unknown hook location.');
        replacement = decode(op.data);
      } else if (op.kind === 'preset-bank') {
        need(op.id === 'licensed-starters' && offset === BANK_START && offset+length === BANK_END, 'Invalid starter bank location.');
        replacement = decode(op.data, 153000);
        await validateStarters(replacement, r);
      } else {
        need(op.kind === 'fill' && op.value === 255 &&
          (op.id === 'empty-global-settings' && offset === GLOBAL_START && offset+length === GLOBAL_END), 'Invalid storage operation.');
        replacement = new Uint8Array(length).fill(255);
      }
      need(replacement.length === length && await sha(replacement) === op.sha256, 'Builder payload checksum mismatch.');
      need(await sha(parsed.payload.subarray(offset, offset+length)) === op.before_sha256, 'Patch-site checksum mismatch.');
      payload.set(replacement, offset); spans.push([offset, offset+length]);
    }
    need(equal(payload.subarray(0,0x400), parsed.payload.subarray(0,0x400)), 'Vector table changed.');
    need(equal(payload.subarray(0x95a4,0x95e8), parsed.payload.subarray(0x95a4,0x95e8)), 'IRQ body changed.');
    need(await sha(payload) === r.output.payload_sha256, 'Generated payload failed verification.');
    const result = original.slice();
    for (let i = 0; i < PAYLOAD_BYTES / 512; i++)
      result.set(payload.subarray(i*512, (i+1)*512), parsed.bina.offset+(i+1)*540+28);
    const digest = await sha(result);
    need(digest === r.output.sha256, 'Generated firmware failed verification. No file will be offered.');
    return { bytes: result, name: r.output.name, report: {
      schema: 'mighty-nam-local-build-report-1', builder_version: r.builder_version,
      identity: r.identity, target: r.target, stock_sha256: INPUT_SHA,
      output_sha256: digest, output_bytes: result.length, recipe_elf_sha256: r.elf_sha256,
      presets: r.presets, captures_included: true,
      starter_presets: r.starter_presets.map(p => ({color:p.color,name:p.name,model_sha256:p.model_sha256})),
      capture_license: 'MIT © 2026 Matt Hartman; see RIFFSMITH-LICENSE',
      license_notices: r.license_notices, original_file_changed: false,
      built_locally: true, device_access: false, flashed: false, hardware_verified: false,
      limitations: ['Three-starter variant verified offline; NAMLNK23 core has limited device validation. Physical pitch timing and Logic duplex remain unverified.',
        'Installation replaces onboard presets and global settings with three RiffSmith A2 Lite starters and four empty colors.',
        'Combined image contains user-supplied NUX firmware; it is not wholly MIT licensed. Keep it local.',
        'Recovery depends on a reachable updater; not guaranteed.']
    }};
  }
  const api = Object.freeze({ inspect, build, sha, inputBytes: INPUT_BYTES, inputSha256: INPUT_SHA });
  root.MightyNamBuilder = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(globalThis);
