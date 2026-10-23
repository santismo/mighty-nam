/* MIT © 2026 santismo. All firmware processing stays in this browser. */
'use strict';
(() => {
  const input = document.querySelector('#stock-file'), button = document.querySelector('#build');
  const status = document.querySelector('#build-status'), result = document.querySelector('#result');
  const fileLink = document.querySelector('#firmware-download'), reportLink = document.querySelector('#report-download');
  let generation = 0, selected = null, urls = [];
  function clearResult() {
    result.hidden = true;
    urls.forEach(url => URL.revokeObjectURL(url)); urls = [];
    fileLink.removeAttribute('href'); reportLink.removeAttribute('href');
  }
  function message(text, error = false) {
    status.textContent = text; status.classList.toggle('error', error);
  }
  input.addEventListener('change', async () => {
    const token = ++generation; selected = null; button.disabled = true; clearResult();
    const file = input.files[0];
    if (!file) { message('Choose your stock firmware to begin.'); return; }
    try {
      if (file.size !== MightyNamBuilder.inputBytes) throw new Error('Unsupported file size. Extract the public NUX V3.0.5 ZIP and select MP3_OR_V3.0.5.bin (Original).');
      message('Checking firmware…');
      const data = new Uint8Array(await file.arrayBuffer());
      const checked = await MightyNamBuilder.inspect(data);
      if (token !== generation) return;
      selected = data; button.disabled = false;
      message('Verified ' + checked.version + '. Ready to build locally.');
    } catch (error) { if (token === generation) message(error.message, true); }
  });
  button.addEventListener('click', async () => {
    if (!selected || button.disabled) return;
    const token = generation; button.disabled = true; input.disabled = true; clearResult();
    message('Building and checking the output…');
    try {
      const built = await MightyNamBuilder.build(selected, MightyNamRecipe);
      if (token !== generation) return;
      const firmwareURL = URL.createObjectURL(new Blob([built.bytes], {type:'application/octet-stream'}));
      const reportURL = URL.createObjectURL(new Blob([JSON.stringify(built.report, null, 2)+'\n'], {type:'application/json'}));
      urls = [firmwareURL, reportURL];
      fileLink.href = firmwareURL; fileLink.download = built.name;
      reportLink.href = reportURL; reportLink.download = 'mighty-nam-'+built.report.identity+'-build-report.json';
      document.querySelector('#output-hash').textContent = built.report.output_sha256;
      result.hidden = false;
      message('Build verified. Save the firmware and report below. Nothing has been installed.');
    } catch (error) { message(error.message, true); }
    finally { input.disabled = false; button.disabled = !selected; }
  });
  if (!globalThis.crypto?.subtle) {
    input.disabled = true;
    message('Open the HTTPS builder or use a modern desktop browser for the offline copy.', true);
  }
})();
