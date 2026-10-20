'use strict';
// The guide's illustration is local only. It never connects to MIDI or audio.
const toggle = document.querySelector('.menu-toggle');
const nav = document.querySelector('#main-nav');
if (toggle && nav) {
  const close = () => { toggle.setAttribute('aria-expanded', 'false'); nav.classList.remove('open'); };
  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    toggle.setAttribute('aria-expanded', String(open)); nav.classList.toggle('open', open);
  });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') close(); });
  nav.addEventListener('click', event => { if (event.target.closest('a')) close(); });
}
const names = { Gate: ['Noise gate', 'Keep the spaces between notes quiet.', ['Threshold', 'Decay', 'Level']], Comp: ['Compressor', 'Control dynamics before the capture.', ['Sustain', 'Attack', 'Level']], Drive: ['Drive', 'Shape the signal going into your amp.', ['Drive', 'Tone', 'Level']], NAM: ['Neural Amp Modeler', 'Your chosen capture, in your signal chain.', ['Input', 'Mix', 'Output']], Cab: ['Cabinet', 'Use with an amp-head capture.', ['Low cut', 'High cut', 'Level']], EQ: ['Equalizer', 'Make room for your guitar.', ['Bass', 'Middle', 'Treble']], Mod: ['Modulation', 'Add movement to the signal.', ['Rate', 'Depth', 'Mix']], Delay: ['Delay', 'Repeats after the note.', ['Time', 'Feedback', 'Mix']], Reverb: ['Reverb', 'Give the sound a space.', ['Decay', 'Tone', 'Mix']] };
const bypass = document.querySelector('#demo-bypass');
const states = {};
let selected = 'NAM';
function renderBlock() {
  const data = names[selected];
  document.querySelector('#demo-title').textContent = data[0];
  document.querySelector('#demo-description').textContent = data[1];
  data[2].forEach((label, i) => { document.querySelector(`#control-label-${i+1}`).textContent = label; document.querySelectorAll('.demo-controls input')[i].setAttribute('aria-label', `Preview ${label.toLowerCase()} control`); });
  const enabled = states[selected] !== false;
  bypass.setAttribute('aria-pressed', String(enabled));
  bypass.firstChild.textContent = enabled ? 'Enabled ' : 'Bypassed ';
  document.querySelectorAll('.demo-block').forEach(button => { button.classList.toggle('selected', button.dataset.block === selected); button.setAttribute('aria-pressed', String(button.dataset.block === selected)); button.classList.toggle('off', states[button.dataset.block] === false); });
}
document.querySelectorAll('.demo-block').forEach(button => button.addEventListener('click', () => { selected = button.dataset.block; renderBlock(); }));
if (bypass) bypass.addEventListener('click', () => { states[selected] = states[selected] === false; renderBlock(); });
document.querySelectorAll('.preset-dot').forEach(button => button.addEventListener('click', () => { document.querySelectorAll('.preset-dot').forEach(item => item.setAttribute('aria-pressed', String(item === button))); document.querySelector('#demo-preset').textContent = button.dataset.color; document.querySelector('#demo-preset-index').textContent = String([...document.querySelectorAll('.preset-dot')].indexOf(button) + 1).padStart(2, '0'); }));
document.querySelectorAll('.demo-controls input').forEach(input => input.addEventListener('input', () => { input.parentElement.querySelector('output').textContent = input.value; }));
