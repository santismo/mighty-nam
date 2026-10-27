/* MIT © 2026 santismo. All firmware processing stays in this browser. */
'use strict';
(() => {
  const input = document.querySelector('#stock-file'), button = document.querySelector('#build');
  const status = document.querySelector('#build-status'), result = document.querySelector('#result');
  const version = document.querySelector('#firmware-version');
  const fileLink = document.querySelector('#firmware-download'), reportLink = document.querySelector('#report-download');
  const recipes = globalThis.MightyNamRecipes || {[MightyNamRecipe.identity]: MightyNamRecipe};
  let recipe = MightyNamRecipe, generation = 0, selected = null, building = false, urls = [];
  const summaries = {
    NAMLNK29:'NAM-only revision 2: seven starter colors, refreshed preset readback, lanes and undo/redo. Offline tested; hardware trial pending.',
    NAMLNK28:'Earlier looper with merged overdubs and saved loop settings. No separate lanes or undo.',
    NAMLNK23:'Earlier Bluetooth playback fix, NAM and effects. No looper or Daisy-derived Auto Wah.'
  };
  function clearResult() {
    result.hidden = true;
    urls.forEach(url => URL.revokeObjectURL(url)); urls = [];
    fileLink.removeAttribute('href'); reportLink.removeAttribute('href');
  }
  function message(text, error = false) {
    status.textContent = text; status.classList.toggle('error', error);
  }
  function chooseVersion() {
    const next = version ? recipes[version.value] : recipe;
    if (building || !next) return;
    recipe = next; clearResult();
    button.textContent = 'Build ' + recipe.identity;
    const note = document.querySelector('#version-description');
    if (note) note.textContent = summaries[recipe.identity];
    document.querySelectorAll('[data-build-identity]').forEach(node => node.textContent = recipe.identity);
    document.querySelectorAll('[data-build-filename]').forEach(node => node.textContent = recipe.output.name);
    if (selected) message('Verified V3.0.5 Original. Ready to build ' + recipe.identity + ' locally.');
  }
  if (version) {
    // A known explicit selection may be bookmarked. Unknown versions fall back to 29.
    const requested = new URLSearchParams(location.search).get('firmware');
    version.value = recipes[requested] ? requested : 'NAMLNK29';
    version.addEventListener('change', chooseVersion);
  }
  chooseVersion();
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
      message('Verified ' + checked.version + '. Ready to build ' + recipe.identity + ' locally.');
    } catch (error) { if (token === generation) message(error.message, true); }
  });
  button.addEventListener('click', async () => {
    if (!selected || button.disabled || building) return;
    const token = generation, chosen = recipe;
    building = true; button.disabled = true; input.disabled = true;
    if (version) version.disabled = true;
    clearResult(); message('Building ' + chosen.identity + ' and checking the output…');
    try {
      const built = await MightyNamBuilder.build(selected, chosen);
      if (token !== generation) return;
      const firmwareURL = URL.createObjectURL(new Blob([built.bytes], {type:'application/octet-stream'}));
      const reportURL = URL.createObjectURL(new Blob([JSON.stringify(built.report, null, 2)+'\n'], {type:'application/json'}));
      urls = [firmwareURL, reportURL];
      fileLink.href = firmwareURL; fileLink.download = built.name;
      reportLink.href = reportURL; reportLink.download = 'mighty-nam-'+built.report.identity+'-build-report.json';
      document.querySelector('#output-hash').textContent = built.report.output_sha256;
      result.hidden = false;
      message(built.report.identity + ' verified. Save the firmware and report below. Nothing has been installed.');
    } catch (error) { message(error.message, true); }
    finally { building = false; input.disabled = false; button.disabled = !selected; if (version) version.disabled = false; }
  });
  if (!globalThis.crypto?.subtle) {
    input.disabled = true;
    message('Open the HTTPS builder or use a modern desktop browser for the offline copy.', true);
  }
})();
