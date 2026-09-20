const steps = [
  ['outcomes', 'Define terminal outcomes for three recurring workflows.'],
  ['traces', 'Instrument complete traces with model, tool, retrieval, latency and outcome references.'],
  ['evals', 'Freeze a representative replay set and a holdout slice.'],
  ['baseline', 'Replay the same cases against one strong hosted model and one local candidate.'],
  ['router', 'Write explicit local / frontier routing rules tied to quality thresholds.'],
  ['adapters', 'Train one narrow, versioned adapter while keeping the base model frozen.'],
  ['promotion', 'Require a promotion receipt and verified rollback target.']
];
const checks = [...document.querySelectorAll('#checks input')];
const nextBox = document.getElementById('next');
const bar = document.getElementById('bar');
const title = document.getElementById('stateTitle');
function getState() {
  const result = {};
  checks.forEach((box) => { result[box.dataset.key] = box.checked; });
  return result;
}
function render() {
  const state = getState();
  const complete = steps.filter(([key]) => state[key]).length;
  const missing = steps.filter(([key]) => !state[key]);
  bar.style.width = `${complete / steps.length * 100}%`;
  title.textContent = complete === steps.length ? 'Loop operational' : `Your next ${Math.min(7, missing.length)} move${missing.length === 1 ? '' : 's'}`;
  if (missing.length) {
    nextBox.innerHTML = '<ol>' + missing.map(([, action]) => `<li>${action}</li>`).join('') + '</ol>';
  } else {
    nextBox.innerHTML = '<p><strong>Now resist adding complexity.</strong> Run the loop, accumulate failures, and promote only changes that clear the frozen evidence.</p>';
  }
  localStorage.setItem('owned-loop-state', JSON.stringify(state));
}
try {
  const saved = JSON.parse(localStorage.getItem('owned-loop-state') || '{}');
  checks.forEach((box) => { box.checked = Boolean(saved[box.dataset.key]); });
} catch (_) {}
checks.forEach((box) => box.addEventListener('change', render));
document.getElementById('reset').addEventListener('click', () => {
  checks.forEach((box) => { box.checked = false; });
  render();
});
document.getElementById('download').addEventListener('click', () => {
  const state = getState();
  const payload = {
    schema: 'axm/owned-learning-loop-plan@1',
    created_at: new Date().toISOString(),
    source: 'https://bigbirdreturns.github.io/axm-tools/owned-learning-loop/',
    state,
    next_steps: steps.filter(([key]) => !state[key]).map(([key, action]) => ({ key, action }))
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'owned-learning-loop-plan.json';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
render();
