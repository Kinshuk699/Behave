/* ═══════════════════════════════════════════════════════════
   Behave — Dashboard JS
   Handles: pre-loaded data render, radar chart, live simulation
   ═══════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
  const data = JSON.parse(document.getElementById('preloadedData').textContent);
  renderPersonas(data.personas);
  renderSegments(data.scorecard.segments);
  renderVerbatims(data.scorecard.top_verbatims);
  renderPlaybook(data.recommendation.edit_recommendations);
  renderEvidence(data.recommendation.key_evidence);
  drawRadar('radarChart', data.scorecard);
  setupTestForm();
});

/* ── Personas list ────────────────────────────────────────── */

function renderPersonas(personas) {
  const el = document.getElementById('personaList');
  if (!el || !personas) return;
  el.innerHTML = personas.map(p => `
    <div class="persona-card">
      <div>
        <div class="persona-card__name">${esc(p.name)}</div>
        <div class="persona-card__meta">${esc(p.city)}</div>
      </div>
      <div class="persona-card__archetype">${esc(p.archetype.replace(/_/g, ' '))}</div>
    </div>
  `).join('');
}

/* ── Segments ─────────────────────────────────────────────── */

function renderSegments(segments) {
  const el = document.getElementById('segmentGrid');
  if (!el || !segments) return;
  el.innerHTML = segments.map(s => `
    <div class="segment-card">
      <div class="segment-card__header">
        <span class="segment-card__name">${esc(s.segment_name.replace(/_/g, ' '))}</span>
        <span class="segment-card__score">${s.avg_score.toFixed(1)}</span>
      </div>
      <div class="segment-card__dims">
        <span class="segment-dim">ATT ${s.avg_attention.toFixed(1)}</span>
        <span class="segment-dim">REL ${s.avg_relevance.toFixed(1)}</span>
        <span class="segment-dim">TRU ${s.avg_trust.toFixed(1)}</span>
        <span class="segment-dim">DES ${s.avg_desire.toFixed(1)}</span>
        <span class="segment-dim">CLA ${s.avg_clarity.toFixed(1)}</span>
      </div>
      <div class="segment-card__verbatim">${esc(s.representative_verbatim)}</div>
    </div>
  `).join('');
}

/* ── Verbatims ────────────────────────────────────────────── */

function renderVerbatims(verbatims) {
  const el = document.getElementById('verbatimList');
  if (!el || !verbatims) return;
  el.innerHTML = verbatims.map(v => `
    <div class="verbatim-card">
      <div class="verbatim-card__text">${esc(v)}</div>
    </div>
  `).join('');
}

/* ── Edit Playbook ────────────────────────────────────────── */

function renderPlaybook(edits) {
  const el = document.getElementById('playbookList');
  if (!el || !edits) return;
  el.innerHTML = edits.map(e => `
    <div class="playbook-card">
      <div class="playbook-card__priority">${e.priority}</div>
      <div>
        <div class="playbook-card__element">${esc(e.element)}</div>
        <div class="playbook-card__current">Now: ${esc(e.current_state)}</div>
        <div class="playbook-card__change">→ ${esc(e.suggested_change)}</div>
        <div class="playbook-card__impact">${esc(e.expected_impact)}</div>
      </div>
    </div>
  `).join('');
}

/* ── Evidence ─────────────────────────────────────────────── */

function renderEvidence(evidence) {
  const el = document.getElementById('evidenceList');
  if (!el || !evidence) return;
  el.innerHTML = evidence.map(e => `<li>${esc(e)}</li>`).join('');
}

/* ── Radar Chart (Canvas) ─────────────────────────────────── */

function drawRadar(canvasId, scorecard) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  const cx = W / 2;
  const cy = H / 2;
  const R = Math.min(W, H) * 0.38;

  const dims = [
    { label: 'Attention', val: scorecard.avg_attention },
    { label: 'Relevance', val: scorecard.avg_relevance },
    { label: 'Trust', val: scorecard.avg_trust },
    { label: 'Desire', val: scorecard.avg_desire },
    { label: 'Clarity', val: scorecard.avg_clarity },
  ];
  const n = dims.length;
  const angleStep = (2 * Math.PI) / n;
  const startAngle = -Math.PI / 2;

  function pointAt(i, r) {
    const angle = startAngle + i * angleStep;
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  }

  // Grid rings
  ctx.strokeStyle = '#222233';
  ctx.lineWidth = 1;
  for (let level = 1; level <= 5; level++) {
    const r = (level / 10) * R;
    ctx.beginPath();
    for (let i = 0; i <= n; i++) {
      const p = pointAt(i % n, r);
      i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y);
    }
    ctx.closePath();
    ctx.stroke();
  }

  // Outer ring (10)
  ctx.strokeStyle = '#333355';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let i = 0; i <= n; i++) {
    const p = pointAt(i % n, R);
    i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y);
  }
  ctx.closePath();
  ctx.stroke();

  // Axes
  ctx.strokeStyle = '#222233';
  ctx.lineWidth = 1;
  for (let i = 0; i < n; i++) {
    const p = pointAt(i, R);
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
  }

  // Data polygon
  ctx.fillStyle = 'rgba(59, 130, 246, 0.12)';
  ctx.strokeStyle = '#3b82f6';
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  for (let i = 0; i <= n; i++) {
    const val = dims[i % n].val;
    const r = (val / 10) * R;
    const p = pointAt(i % n, r);
    i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y);
  }
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  // Data dots
  ctx.fillStyle = '#3b82f6';
  for (let i = 0; i < n; i++) {
    const r = (dims[i].val / 10) * R;
    const p = pointAt(i, r);
    ctx.beginPath();
    ctx.arc(p.x, p.y, 4, 0, 2 * Math.PI);
    ctx.fill();
  }

  // Labels
  ctx.fillStyle = '#8888a0';
  ctx.font = '13px "DM Sans", sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  for (let i = 0; i < n; i++) {
    const p = pointAt(i, R + 24);
    ctx.fillText(dims[i].label, p.x, p.y);
  }

  // Score values
  ctx.fillStyle = '#e8e8ed';
  ctx.font = 'bold 12px "DM Sans", sans-serif';
  for (let i = 0; i < n; i++) {
    const r = (dims[i].val / 10) * R;
    const p = pointAt(i, r + 16);
    ctx.fillText(dims[i].val.toFixed(1), p.x, p.y);
  }
}

/* ── Test Form ────────────────────────────────────────────── */

function setupTestForm() {
  const gate = document.getElementById('testGate');
  const form = document.getElementById('testForm');
  const gateBtn = document.getElementById('gateBtn');
  const uploadZone = document.getElementById('uploadZone');
  const inputImage = document.getElementById('inputImage');
  const runBtn = document.getElementById('runBtn');

  let savedPassword = '';
  let imageBase64 = '';

  // Password gate
  gateBtn.addEventListener('click', () => {
    const pw = document.getElementById('gatePassword').value;
    if (pw.length > 0) {
      savedPassword = pw;
      gate.style.display = 'none';
      form.style.display = 'block';
    }
  });

  // Upload zone
  uploadZone.addEventListener('click', () => inputImage.click());
  uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.style.borderColor = '#3b82f6'; });
  uploadZone.addEventListener('dragleave', () => { uploadZone.style.borderColor = ''; });
  uploadZone.addEventListener('drop', e => {
    e.preventDefault();
    uploadZone.style.borderColor = '';
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
  });
  inputImage.addEventListener('change', () => {
    if (inputImage.files.length) handleFile(inputImage.files[0]);
  });

  function handleFile(file) {
    if (!file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = () => {
      imageBase64 = reader.result.split(',')[1];
      const preview = document.getElementById('imagePreview');
      preview.innerHTML = `<img src="${reader.result}" alt="preview">`;
      preview.style.display = 'block';
      uploadZone.style.display = 'none';
    };
    reader.readAsDataURL(file);
  }

  // Run simulation
  runBtn.addEventListener('click', async () => {
    const brand = document.getElementById('inputBrand').value.trim();
    const category = document.getElementById('inputCategory').value.trim();
    if (!brand || !category) {
      showStatus('Brand and category are required.', 'error');
      return;
    }

    runBtn.disabled = true;
    showStatus('Running simulation… This takes 30–90 seconds.', 'loading');

    try {
      const body = {
        password: savedPassword,
        brand,
        category,
        headline: document.getElementById('inputHeadline').value.trim(),
        body_copy: document.getElementById('inputBody').value.trim(),
        cta: document.getElementById('inputCta').value.trim(),
        memory_scope: document.getElementById('inputScope').value,
        cohort_size: parseInt(document.getElementById('inputCohort').value, 10),
        image_base64: imageBase64,
      };

      const resp = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (resp.status === 403) {
        showStatus('Invalid password.', 'error');
        runBtn.disabled = false;
        return;
      }
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
        showStatus(`Error: ${err.detail}`, 'error');
        runBtn.disabled = false;
        return;
      }

      const result = await resp.json();
      renderLiveResults(result);
      showStatus('Simulation complete!', 'loading');
      runBtn.disabled = false;
    } catch (e) {
      showStatus(`Network error: ${e.message}`, 'error');
      runBtn.disabled = false;
    }
  });
}

function showStatus(msg, type) {
  const el = document.getElementById('testStatus');
  el.style.display = 'block';
  el.className = `test__status test__status--${type}`;
  el.textContent = msg;
}

/* ── Live Results Render ──────────────────────────────────── */

function renderLiveResults(result) {
  const container = document.getElementById('testResults');
  container.style.display = 'block';

  const sc = result.scorecards && result.scorecards[0];
  const rec = result.recommendation;
  const meta = result.metadata;

  // Verdict banner
  const action = rec ? rec.recommended_action : (sc ? sc.grade : 'N/A');
  const verdictClass = action === 'kill' ? 'kill' : action === 'scale' ? 'scale' : 'iterate';
  const liveVerdict = document.getElementById('liveVerdict');
  liveVerdict.innerHTML = `
    <div class="verdict__banner verdict__banner--${verdictClass}">
      <div class="verdict__action">${esc(action.toUpperCase())}</div>
      <div class="verdict__confidence">${rec ? Math.round(rec.confidence_score * 100) + '% confidence' : ''}</div>
      <div class="verdict__reason">${rec ? esc(rec.reasoning_summary) : ''}</div>
    </div>
    <div class="pipeline__stats" style="margin-bottom:2rem;">
      <div class="pipeline__stat"><span class="pipeline__stat-num">${sc ? sc.overall_score.toFixed(1) : '-'}</span><span class="pipeline__stat-label">Score</span></div>
      <div class="pipeline__stat"><span class="pipeline__stat-num">${sc ? sc.grade : '-'}</span><span class="pipeline__stat-label">Grade</span></div>
      <div class="pipeline__stat"><span class="pipeline__stat-num">$${meta ? meta.total_cost_usd.toFixed(3) : '-'}</span><span class="pipeline__stat-label">Cost</span></div>
      <div class="pipeline__stat"><span class="pipeline__stat-num">${meta ? meta.total_tokens : '-'}</span><span class="pipeline__stat-label">Tokens</span></div>
    </div>
  `;

  // Radar chart
  if (sc) {
    drawRadar('liveRadarChart', {
      avg_attention: sc.avg_attention,
      avg_relevance: sc.avg_relevance,
      avg_trust: sc.avg_trust,
      avg_desire: sc.avg_desire,
      avg_clarity: sc.avg_clarity,
    });

    // Dimensions
    const liveDims = document.getElementById('liveDimensions');
    const dims = [
      ['Attention', sc.avg_attention],
      ['Relevance', sc.avg_relevance],
      ['Trust', sc.avg_trust],
      ['Desire', sc.avg_desire],
      ['Clarity', sc.avg_clarity],
    ];
    liveDims.innerHTML = dims.map(([name, val]) => `
      <div class="dim">
        <span class="dim__name">${name}</span>
        <div class="dim__bar-track"><div class="dim__bar" style="--pct: ${val * 10}%; width: ${val * 10}%"></div></div>
        <span class="dim__val">${val.toFixed(1)}</span>
      </div>
    `).join('');
  }

  // Verbatims from evaluations
  const liveVerbatims = document.getElementById('liveVerbatims');
  if (result.evaluations && result.evaluations.length) {
    liveVerbatims.innerHTML = `
      <h3 class="verdict__sub-title" style="margin-top:2rem;">Verbatim Reactions</h3>
      <div class="verbatims__list">
        ${result.evaluations.map(e => `
          <div class="verbatim-card">
            <div class="verbatim-card__text">${esc(e.verbatim_reaction || e.first_impression || '')}</div>
          </div>
        `).join('')}
      </div>
    `;
  }

  // Edit playbook
  const livePlaybook = document.getElementById('livePlaybook');
  if (rec && rec.edit_recommendations) {
    renderPlaybookInto(livePlaybook, rec.edit_recommendations);
  }
}

function renderPlaybookInto(el, edits) {
  el.innerHTML = `
    <h3 class="verdict__sub-title" style="margin-top:2rem;">Edit Playbook</h3>
    <div class="playbook__list">
      ${edits.map(e => `
        <div class="playbook-card">
          <div class="playbook-card__priority">${e.priority}</div>
          <div>
            <div class="playbook-card__element">${esc(e.element)}</div>
            <div class="playbook-card__current">Now: ${esc(e.current_state)}</div>
            <div class="playbook-card__change">→ ${esc(e.suggested_change)}</div>
            <div class="playbook-card__impact">${esc(e.expected_impact)}</div>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

/* ── Utilities ─────────────────────────────────────────────── */

function esc(str) {
  if (!str) return '';
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
