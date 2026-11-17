(function () {
  'use strict';
  var D = window.P2;
  var FAM = [
    { k: 'qwen', name: 'Qwen 3.5 27B', std: 'qwen3.5-27b-standard', abl: 'qwen3.5-27b-abliterated', shape: 'circle' },
    { k: 'llama', name: 'Llama 3.1 8B', std: 'llama3.1-8b-standard', abl: 'llama3.1-8b-abliterated', shape: 'square' },
    { k: 'gemma', name: 'Gemma 4 12B', std: 'gemma4-12b-standard', abl: 'gemma4-12b-abliterated', shape: 'triangle' }
  ];
  var famOf = {}; FAM.forEach(function (f) { famOf[f.std] = f; famOf[f.abl] = f; });
  var PROMPTS = {}; D.prompts.forEach(function (p) { PROMPTS[p.id] = p; });
  var state = { runset: 'sampled', cond: 'original', ppfam: 'qwen', ppword: 'original', swword: 'original', swrun: 'sampled', swprompt: '' };
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function n0(x) { return Math.round(x).toLocaleString('en-US'); }
  function pct(x) { return Math.round(x * 100) + '%'; }
  function r2(x) { return x.toFixed(2) + '×'; }
  function variantOf(m) { return /abliterated/.test(m) ? 'abl' : 'std'; }
  function m(model) { return D.by_model[model][state.runset][state.cond]; }
  function svgEl(w, h, inner, label) { return '<svg viewBox="0 0 ' + w + ' ' + h + '" width="' + w + '" height="' + h + '" role="img" aria-label="' + esc(label) + '">' + inner + '</svg>'; }
  function width(el) { return Math.max(280, Math.floor(el.getBoundingClientRect().width)); }

  /* ---------- tooltip ---------- */
  var tip = $('tip');
  function showTip(html, ev) {
    tip.innerHTML = html; tip.hidden = false;
    var x = ev.clientX + 14, y = ev.clientY + 14, r = tip.getBoundingClientRect();
    if (x + r.width > window.innerWidth - 8) x = ev.clientX - r.width - 14;
    if (y + r.height > window.innerHeight - 8) y = ev.clientY - r.height - 14;
    tip.style.left = Math.max(8, x) + 'px'; tip.style.top = Math.max(8, y) + 'px';
  }
  function hideTip() { tip.hidden = true; }
  function bindTips(root, fn) {
    root.addEventListener('pointermove', function (ev) { var t = ev.target.closest('[data-tip]'); if (t) showTip(fn(t), ev); else hideTip(); });
    root.addEventListener('pointerleave', hideTip);
  }

  /* ---------- segmented controls ---------- */
  document.querySelectorAll('.seg[data-ctl]').forEach(function (seg) {
    var key = seg.getAttribute('data-ctl');
    seg.addEventListener('click', function (ev) {
      var b = ev.target.closest('button'); if (!b) return;
      state[key] = b.getAttribute('data-v');
      seg.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
      render(key);
    });
  });

  /* ---------- tiles ---------- */
  function renderTiles() {
    var rat = D.ratios.sampled.original.tpua;
    var caps = FAM.map(function (f) { return (D.capability.per_model[f.abl].accuracy - D.capability.per_model[f.std].accuracy) * 100; });
    var capMin = Math.max.apply(null, caps), capMax = Math.min.apply(null, caps);
    var capN = Object.keys(D.capability.per_model).reduce(function (s, k) { return s + D.capability.per_model[k].n; }, 0);
    $('tiles').innerHTML = [
      '<div class="tile"><b>' + n0(D.answers.length) + '</b><span>answers from 6 models, each graded by a separate judge</span><small>' + D.judge.errors + ' judge errors, ' + D.judge.missing + ' missing</small></div>',
      '<div class="tile"><b>' + r2(rat.mean_of_family_ratios) + '</b><span>tokens per useful answer, abliterated vs standard</span><small>mean of 3 within-family ratios, sampled, original wording</small></div>',
      '<div class="tile"><b>' + caps.filter(function (c) { return c < 0; }).length + ' of 3</b><span>abliterated copies scored lower on the capability check</span><small>' + capMin.toFixed(1).replace('-', '\u2212') + ' to ' + capMax.toFixed(1).replace('-', '\u2212') + ' points, ' + n0(capN) + ' items in all</small></div>',
      '<div class="tile"><b>' + D.verify.fails + ' FAIL</b><span>in the verifier’s recheck of every summary number</span><small>' + D.verify.warnings + ' WARN: correction turns not judged</small></div>'
    ].join('');
  }

  /* ---------- family cards ---------- */
  var condNotes = {
    original: 'The prompt as written, trigger word included.',
    twin: 'The same request with the trigger word swapped for a neutral one ("kill" → "clean up").',
    block: 'A keyword filter blocks 9 of 10 originals at 0 model tokens, and the user re-asks with the twin. These are the tokens of the answer the user finally gets.'
  };
  function hbar(cls, label, v, max, txt, think) {
    var w = max > 0 ? (v / max * 100) : 0;
    var t = think != null && v > 0 ? (think / v * 100) : 0;
    return '<div class="hb ' + cls + '"><span>' + label + '</span><div class="hb-track"><div class="hb-fill" data-w="' + w.toFixed(2) + '">' +
      (think != null ? '<div class="hb-think" style="width:' + t.toFixed(2) + '%"></div>' : '') + '</div></div><span class="hb-v">' + txt + '</span></div>';
  }
  function renderFamilies() {
    $('condNote').textContent = condNotes[state.cond];
    var html = FAM.map(function (f) {
      var s = m(f.std), a = m(f.abl);
      var outMax = Math.max(s.mean_output_tokens, a.mean_output_tokens);
      var tMax = Math.max(s.tpua.value, a.tpua.value);
      var hasThink = s.mean_thinking_tokens_est > 0 || a.mean_thinking_tokens_est > 0;
      var foot = '';
      if (f.k === 'llama') foot = '<p class="fam-foot">Recorded mean input per prompt: ' + n0(s.mean_input_tokens) + ' tokens (standard) vs ' + n0(a.mean_input_tokens) + ' (abliterated). Llama 3.1 has no thinking mode.</p>';
      return '<article class="fam"><h3>' + f.name + '</h3><p class="repo">' + esc(D.repos[f.std]) + '<br>' + esc(D.repos[f.abl]) + '</p>' +
        '<div class="metric"><div class="metric-h"><span>Mean output tokens' + (hasThink ? ', thinking hatched' : '') + '</span><span class="ratio-chip">' + r2(a.mean_output_tokens / s.mean_output_tokens) + '</span></div>' +
        hbar('a', 'Std', s.mean_output_tokens, outMax, n0(s.mean_output_tokens), hasThink ? s.mean_thinking_tokens_est : null) +
        hbar('b', 'Abl', a.mean_output_tokens, outMax, n0(a.mean_output_tokens), hasThink ? a.mean_thinking_tokens_est : null) + '</div>' +
        '<div class="metric"><div class="metric-h"><span>Judged useful</span><span class="ratio-chip">' + (a.useful_rate >= s.useful_rate ? '+' : '−') + Math.abs(Math.round((a.useful_rate - s.useful_rate) * 100)) + ' pts</span></div>' +
        hbar('a', 'Std', s.useful_rate, 1, pct(s.useful_rate)) + hbar('b', 'Abl', a.useful_rate, 1, pct(a.useful_rate)) + '</div>' +
        '<div class="metric"><div class="metric-h"><span>Tokens per useful answer (TPUA)</span><span class="ratio-chip">' + r2(a.tpua.value / s.tpua.value) + '</span></div>' +
        hbar('a', 'Std', s.tpua.value, tMax, n0(s.tpua.value)) + hbar('b', 'Abl', a.tpua.value, tMax, n0(a.tpua.value)) +
        '<p class="tpua-frac">std ' + n0(s.tpua.numerator_tokens) + ' / ' + s.tpua.denominator_useful + ' useful &middot; abl ' + n0(a.tpua.numerator_tokens) + ' / ' + a.tpua.denominator_useful + ' useful</p></div>' +
        foot + '</article>';
    }).join('');
    var grid = $('famGrid'); grid.innerHTML = html;
    var fills = grid.querySelectorAll('.hb-fill');
    requestAnimationFrame(function () { requestAnimationFrame(function () { fills.forEach(function (el) { el.style.width = el.getAttribute('data-w') + '%'; }); }); });
  }

  /* ---------- ratio chart ---------- */
  function shape(kind, x, y, r, attrs) {
    if (kind === 'square') return '<rect class="mk" x="' + (x - r) + '" y="' + (y - r) + '" width="' + 2 * r + '" height="' + 2 * r + '" rx="1.5" ' + attrs + '/>';
    if (kind === 'triangle') return '<path class="mk" transform="translate(' + x + ',' + y + ')" d="M0,' + (-r * 1.2) + 'L' + r * 1.1 + ',' + r * .8 + 'L' + (-r * 1.1) + ',' + r * .8 + 'Z" ' + attrs + '/>';
    if (kind === 'diamond') return '<path class="mk" transform="translate(' + x + ',' + y + ')" d="M0,' + (-r * 1.3) + 'L' + r * 1.3 + ',0L0,' + r * 1.3 + 'L' + (-r * 1.3) + ',0Z" ' + attrs + '/>';
    return '<circle class="mk" cx="' + x + '" cy="' + y + '" r="' + r + '" ' + attrs + '/>';
  }
  function renderRatios() {
    var el = $('ratioChart'), W = width(el), narrow = W < 600;
    var ml = narrow ? 12 : 170, mr = 20, rowH = narrow ? 78 : 64, top = narrow ? 30 : 34;
    var metrics = [['mean_output_tokens', 'Mean output tokens'], ['mean_thinking_tokens_est', 'Thinking tokens (est.)'], ['tpua', 'Tokens per useful answer']];
    var H = top + metrics.length * rowH + 30;
    var lo = Math.log(0.5), hi = Math.log(4);
    function X(v) { return ml + (Math.log(v) - lo) / (hi - lo) * (W - ml - mr); }
    var ticks = [0.5, 0.75, 1, 1.5, 2, 3, 4], g = '';
    ticks.forEach(function (t) {
      g += '<g class="grid"><line x1="' + X(t) + '" x2="' + X(t) + '" y1="' + (top - 8) + '" y2="' + (H - 26) + '"' + (t === 1 ? ' style="stroke:var(--ink-3);stroke-width:1.5"' : '') + '/></g>';
      g += '<text x="' + X(t) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="12">' + t + '×</text>';
    });
    var dy = narrow ? 12 : top - 16, fs = narrow ? 11 : 12;
    g += '<text x="' + (X(1) - 6) + '" y="' + dy + '" text-anchor="end" font-size="' + fs + '">\u2190 standard more</text><text x="' + (X(1) + 6) + '" y="' + dy + '" font-size="' + fs + '">abliterated more \u2192</text>';
    var R = D.ratios[state.runset][state.cond];
    metrics.forEach(function (mt, i) {
      var y = top + i * rowH + (narrow ? 40 : rowH / 2);
      g += narrow ? '<text x="0" y="' + (y - 22) + '" font-size="13" style="fill:var(--ink);font-weight:600">' + mt[1] + '</text>'
                  : '<text x="0" y="' + (y + 4) + '" font-size="14" style="fill:var(--ink);font-weight:500">' + mt[1] + '</text>';
      g += '<line x1="' + ml + '" x2="' + (W - mr) + '" y1="' + y + '" y2="' + y + '" style="stroke:var(--line)"/>';
      var row = R[mt[0]];
      FAM.forEach(function (f, j) {
        var v = row.by_family[f.k]; if (v == null) return;
        var yy = y + (j - 1) * 9;
        g += shape(f.shape, X(v), yy, 6, 'style="fill:var(--ink-2);stroke:var(--bg);stroke-width:2" data-tip="1" data-l="' + f.name + '" data-m="' + mt[1] + '" data-v="' + v + '"');
      });
      var mv = row.mean_of_family_ratios;
      g += shape('diamond', X(mv), y, 7, 'style="fill:var(--accent);stroke:var(--bg);stroke-width:2" data-tip="1" data-l="Mean of ' + row.n_families + ' families" data-m="' + mt[1] + '" data-v="' + mv + '"');
      g += '<text x="' + (X(mv)) + '" y="' + (y + (narrow ? 30 : 28)) + '" text-anchor="middle" font-size="12" style="fill:var(--ink);font-weight:600;paint-order:stroke;stroke:var(--bg);stroke-width:3px">' + r2(mv) + '</text>';
    });
    var leg = '<div class="legend" style="margin-top:4px"><span>' + FAM.map(function (f) {
      return '<svg width="14" height="14" viewBox="-7 -7 14 14" aria-hidden="true">' + shape(f.shape, 0, 0, 5, 'style="fill:var(--ink-2)"') + '</svg>' + f.name;
    }).join('</span><span>') + '</span><span><svg width="14" height="14" viewBox="-8 -8 16 16" aria-hidden="true">' + shape('diamond', 0, 0, 5, 'style="fill:var(--accent)"') + '</svg>Mean of families</span></div>';
    el.innerHTML = leg + svgEl(W, H, g, 'Within-family ratios, abliterated over standard');
  }
  bindTips($('ratioChart'), function (t) { return '<b>' + esc(t.getAttribute('data-l')) + '</b><br>' + esc(t.getAttribute('data-m')) + ': ' + r2(+t.getAttribute('data-v')) + '<div class="t2">' + state.runset + ', ' + state.cond + '</div>'; });

  /* ---------- observations ---------- */
  function renderObs() {
    var so = D.ratios.sampled, conds = ['original', 'twin', 'block'], allUp = true;
    conds.forEach(function (c) { FAM.forEach(function (f) { if (!(so[c].tpua.by_family[f.k] > 1)) allUp = false; }); });
    var gExc = [];
    conds.forEach(function (c) { FAM.forEach(function (f) { var v = D.ratios.greedy[c].tpua.by_family[f.k]; if (v <= 1) gExc.push(f.name + ' ' + c + ' (' + r2(v) + ')'); }); });
    var bo = function (mod) { return D.by_model[mod].sampled.original; };
    var L = FAM[1], G = FAM[2], Q = FAM[0];
    var ref = {}; D.answers.forEach(function (a) { if (a[6] === 'full_refusal' || a[6] === 'partial_refusal') ref[a[0]] = (ref[a[0]] || 0) + 1; });
    var refTxt = Object.keys(ref).map(function (k) { return famOf[k].name + ' ' + (variantOf(k) === 'std' ? 'standard' : 'abliterated') + ' ' + ref[k]; }).join(', ');
    var capD = FAM.map(function (f) { return f.name + ' ' + ((D.capability.per_model[f.abl].accuracy - D.capability.per_model[f.std].accuracy) * 100).toFixed(1); });
    var nCorr = D.corrections.length, corrModels = {}; D.corrections.forEach(function (c) { corrModels[c.model] = 1; });
    var items = [
      (allUp ? 'In the sampled runs, the abliterated copy used <b>more tokens per useful answer in every family and every condition</b>' : 'In the sampled runs, the abliterated copy mostly used more tokens per useful answer') +
        '. On the original wording the ratios were ' + FAM.map(function (f) { return f.name.split(' ')[0] + ' ' + r2(so.original.tpua.by_family[f.k]); }).join(', ') + '.' +
        (gExc.length ? ' The greedy single runs have ' + (gExc.length === 1 ? 'one exception' : gExc.length + ' exceptions') + ': ' + gExc.join(', ') + '.' : ''),
      'The gap comes mostly from <b>how often an answer was useful, not from how long it was</b>. The Llama abliterated copy wrote fewer tokens (' + r2(bo(L.abl).mean_output_tokens / bo(L.std).mean_output_tokens) + ') but was judged useful ' + pct(bo(L.abl).useful_rate) + ' of the time vs ' + pct(bo(L.std).useful_rate) +
        '. Gemma’s fell from ' + pct(bo(G.std).useful_rate) + ' to ' + pct(bo(G.abl).useful_rate) + ', and Qwen’s from ' + pct(bo(Q.std).useful_rate) + ' to ' + pct(bo(Q.abl).useful_rate) + ' (sampled, original wording).',
      'Judged refusals were <b>rare</b>. Across all 120 answers per model, the judge marked full or partial refusals only here: ' + esc(refTxt) + '. The other models had none. The Llama abliterated copy refused about as often as its standard model.',
      'Every abliterated copy scored lower on the capability check (' + capD.join(', ') + ' points). That fits the proposal’s concern that the downloaded copies are a confound.',
      'All ' + nCorr + ' correction turns came from ' + Object.keys(corrModels).join(', ') + '. They have not been judged, so the pilot <b>cannot yet say whether one follow-up closes the gap</b>.'
    ];
    $('obs').innerHTML = items.map(function (t) { return '<li>' + t + '</li>'; }).join('');
  }

  /* ---------- per prompt ---------- */
  var ppOpen = {};
  function ppRow(fam, variant, pid, word) {
    for (var i = 0; i < D.per_prompt.length; i++) { var r = D.per_prompt[i]; if (r.family === fam && r.variant === variant && r.prompt_id === pid && r.wording === word) return r; }
  }
  function markTrigger(text, trig) {
    if (!trig) return esc(text);
    var i = text.toLowerCase().indexOf(trig.toLowerCase());
    if (i < 0) return esc(text);
    return esc(text.slice(0, i)) + '<mark>' + esc(text.slice(i, i + trig.length)) + '</mark>' + esc(text.slice(i + trig.length));
  }
  function renderPP() {
    var el = $('ppChart'), fam = state.ppfam, word = state.ppword;
    var max = 0; D.per_prompt.forEach(function (r) { if (r.family === fam) max = Math.max(max, r.mean_output_tokens); });
    max = Math.ceil(max / 500) * 500;
    var probe = el.querySelector('.pp-svg'), W = probe ? Math.floor(probe.getBoundingClientRect().width) : 0;
    if (!W) { var tw = width(el); W = tw < 600 ? tw - 62 - 76 - 16 : tw - 150 - 92 - 28; }
    function X(v) { return 8 + v / max * (W - 16); }
    var html = D.prompts.map(function (p) {
      var s = ppRow(fam, 'standard', p.id, word), a = ppRow(fam, 'abliterated', p.id, word);
      var xs = X(s.mean_output_tokens), xa = X(a.mean_output_tokens), lo = Math.min(xs, xa), hi = Math.max(xs, xa);
      var svg = '<svg class="pp-svg" viewBox="0 0 ' + W + ' 28" preserveAspectRatio="none" aria-hidden="true">' +
        '<line x1="8" x2="' + (W - 8) + '" y1="14" y2="14" style="stroke:var(--chart-grid)"/>' +
        '<line x1="' + lo + '" x2="' + hi + '" y1="14" y2="14" style="stroke:var(--ink-3);stroke-width:2"/>' +
        '<circle class="mk" cx="' + xs + '" cy="14" r="6" style="fill:var(--series-a);stroke:var(--bg);stroke-width:2"/>' +
        '<circle class="mk" cx="' + xa + '" cy="14" r="6" style="fill:var(--series-b);stroke:var(--bg);stroke-width:2"/></svg>';
      var detail = '<div class="pp-detail"><div class="qq"><span>Original</span><div>' + markTrigger(p.prompt, p.trigger) + '</div><span>Twin</span><div>' + esc(p.neutral_twin) + '</div><span>Domain</span><div>' + esc(p.domain) + '</div></div>' +
        '<div style="font-size:13px;font-weight:600;color:var(--ink-2)">The judge required</div><ul>' + p.required.map(function (r) { return '<li>' + esc(r) + '</li>'; }).join('') + '</ul>' +
        (p.notes ? '<p class="pp-nums">Note: ' + esc(p.notes) + '</p>' : '') +
        '<p class="pp-nums">Mean output, ' + word + ': standard ' + s.mean_output_tokens.toFixed(1) + ', abliterated ' + a.mean_output_tokens.toFixed(1) + ' (' + r2(a.mean_output_tokens / s.mean_output_tokens) + '). Full refusal: ' + pct(s.full_refusal_rate) + ' / ' + pct(a.full_refusal_rate) + '. n = ' + s.n + ' / ' + a.n + '.</p></div>';
      var trig = p.trigger ? '“' + esc(p.trigger) + '”' : 'no trigger';
      return '<div class="pp-row' + (ppOpen[p.id] ? ' open' : '') + '" data-p="' + p.id + '"><button class="pp-btn" aria-expanded="' + (ppOpen[p.id] ? 'true' : 'false') + '"><span class="pp-id">' + p.id + '<small>' + trig + '</small></span>' + svg +
        '<span class="pp-u">' + pct(s.useful_rate) + ' / ' + pct(a.useful_rate) + '</span></button>' + detail + '</div>';
    }).join('');
    var ticks = [0, max / 2, max].map(function (t) { return n0(t); });
    html += '<div class="pp-axis" aria-hidden="true"><span></span><span style="display:flex;justify-content:space-between"><span>' + ticks.join('</span><span>') + ' tokens</span></span><span></span></div>';
    el.innerHTML = html;
  }
  $('ppChart').addEventListener('click', function (ev) {
    var b = ev.target.closest('.pp-btn'); if (!b) return;
    var row = b.parentNode, id = row.getAttribute('data-p');
    ppOpen[id] = !ppOpen[id]; row.classList.toggle('open', ppOpen[id]); b.setAttribute('aria-expanded', ppOpen[id] ? 'true' : 'false');
  });

  /* ---------- swarm ---------- */
  var swPts = [];
  D.prompts.forEach(function (p) { var o = document.createElement('option'); o.value = p.id; o.textContent = p.id + (p.trigger ? ' · ' + p.trigger : ' · no trigger'); $('swPrompt').appendChild(o); });
  $('swPrompt').addEventListener('change', function () { state.swprompt = this.value; renderSwarm(); });
  function renderSwarm() {
    var el = $('swarmChart'), W = width(el), narrow = W < 600;
    var ml = narrow ? 4 : 190, mr = 14, rowH = narrow ? 84 : 78, top = 8, r = narrow ? 3.2 : 4.2;
    var models = []; FAM.forEach(function (f) { models.push(f.std, f.abl); });
    var H = top + models.length * rowH + (narrow ? 0 : 12) + 30;
    var CAP = 4096;
    function X(v) { return ml + Math.min(v, CAP) / CAP * (W - ml - mr); }
    var g = '';
    [0, 1024, 2048, 3072, 4096].forEach(function (t) {
      g += '<g class="grid"><line x1="' + X(t) + '" x2="' + X(t) + '" y1="' + top + '" y2="' + (H - 26) + '"/></g><text x="' + X(t) + '" y="' + (H - 8) + '" text-anchor="' + (t === 0 ? 'start' : t === 4096 ? 'end' : 'middle') + '" font-size="12">' + n0(t) + (t === 4096 ? ' cap' : '') + '</text>';
    });
    swPts = []; var shown = 0;
    models.forEach(function (mod, i) {
      var f = famOf[mod], v = variantOf(mod), y0 = top + i * rowH + (narrow ? 22 : 0) + (rowH - (narrow ? 22 : 0)) / 2;
      if (i % 2 === 0 && i > 0) g += '<line x1="0" x2="' + W + '" y1="' + (top + i * rowH) + '" y2="' + (top + i * rowH) + '" style="stroke:var(--line)"/>';
      var lab = f.name + (v === 'std' ? ' standard' : ' abliterated');
      g += narrow ? '<text x="' + ml + '" y="' + (top + i * rowH + 16) + '" font-size="12" style="fill:var(--ink);font-weight:500">' + lab + '</text>'
                  : '<text x="0" y="' + (y0 + 4) + '" font-size="13" style="fill:var(--ink)' + (v === 'std' ? ';font-weight:500' : '') + '">' + lab + '</text>';
      var pts = D.answers.map(function (a, idx) { return { a: a, idx: idx }; }).filter(function (o) {
        var a = o.a; return a[0] === mod && a[2] === state.swword && (state.swrun === 'greedy' ? a[3] === 'greedy' : a[3] !== 'greedy') && (!state.swprompt || a[1] === state.swprompt);
      }).sort(function (p, q) { return p.a[4] - q.a[4]; });
      var placed = [], lim = (rowH - (narrow ? 26 : 10)) / 2 - r;
      pts.forEach(function (o) {
        var x = X(o.a[4]), y = y0, k = 0, ok = false;
        while (!ok && k < 40) {
          var off = (k % 2 ? 1 : -1) * Math.ceil(k / 2) * (r * 1.05); y = y0 + off; ok = true;
          for (var j = placed.length - 1; j >= 0; j--) { var pj = placed[j]; if (x - pj[0] > 2 * r + 1) break; if (Math.hypot(x - pj[0], y - pj[1]) < 2 * r + 0.6) { ok = false; break; } }
          if (Math.abs(off) > lim) { y = y0 + Math.max(-lim, Math.min(lim, off)); ok = true; }
          k++;
        }
        placed.push([x, y]);
        var a = o.a, col = v === 'std' ? 'var(--series-a)' : 'var(--series-b)', refused = a[6] === 'full_refusal' || a[6] === 'partial_refusal';
        var fill = a[7] ? col : 'var(--bg)';
        g += (refused ? '<circle cx="' + x + '" cy="' + y + '" r="' + (r + 2.6) + '" style="fill:none;stroke:var(--ink);stroke-width:1.4"/>' : '') +
          '<circle class="mk" cx="' + x + '" cy="' + y + '" r="' + r + '" style="fill:' + fill + ';stroke:' + col + ';stroke-width:' + (a[7] ? 1 : 1.8) + '"/>' +
          '<circle class="hit" cx="' + x + '" cy="' + y + '" r="' + (r + 4) + '" data-tip="1" data-i="' + o.idx + '" tabindex="0" role="button" aria-label="' + esc(lab + ', ' + a[1] + ' ' + a[3] + ', ' + a[4] + ' tokens') + '"/>';
        shown++;
      });
    });
    el.innerHTML = svgEl(W, H, g, 'Every answer, by output tokens');
    $('swarmCount').textContent = shown + ' answers shown. ' + (state.swrun === 'sampled' ? 'Sampled runs s1 to s5 at temperature 0.7.' : 'Greedy runs, one per prompt.') + ' Select a dot, or focus it and press Enter, to read the answer.';
  }
  var refusalName = { full_answer: 'Full answer', partial_refusal: 'Partial refusal', full_refusal: 'Full refusal' };
  bindTips($('swarmChart'), function (t) {
    var a = D.answers[+t.getAttribute('data-i')], f = famOf[a[0]];
    return '<b>' + f.name + ' ' + (variantOf(a[0]) === 'std' ? 'standard' : 'abliterated') + '</b><br>' + a[1] + ' · ' + a[2] + ' · run ' + a[3] +
      '<br>' + n0(a[4]) + ' output tokens' + (a[5] ? ' (~' + n0(a[5]) + ' thinking)' : '') + '<div class="t2">' + (refusalName[a[6]] || 'Not judged') + ' · ' + (a[7] ? 'useful' : 'not useful') + (a[8] ? ' · hit cap' : '') + '</div>';
  });
  function openAnswer(i) {
    var a = D.answers[i], f = famOf[a[0]], p = PROMPTS[a[1]];
    $('sheetKicker').textContent = f.name + ' ' + (variantOf(a[0]) === 'std' ? 'standard' : 'abliterated') + ' · ' + a[1] + ' · ' + a[2] + ' · run ' + a[3];
    $('sheetTitle').textContent = a[2] === 'twin' ? p.neutral_twin : p.prompt;
    var req = a[11] ? p.required.map(function (r, k) { return '<li>' + (a[11][k] ? '✓ ' : '✗ ') + esc(r) + '</li>'; }).join('') : '';
    $('sheetBody').innerHTML = '<div class="kv"><span>' + n0(a[9]) + ' input tokens</span><span>' + n0(a[4]) + ' output tokens</span>' + (a[5] ? '<span>~' + n0(a[5]) + ' thinking (est.)</span>' : '') +
      '<span>' + (refusalName[a[6]] || 'Not judged') + '</span><span>' + (a[7] ? 'Judged useful' : 'Not useful') + '</span>' + (a[10] ? '<span>Materially wrong</span>' : '') + (a[8] ? '<span>Hit the cap</span>' : '') + '</div>' +
      (req ? '<h4>Judge checklist</h4><ul style="font-size:14px;color:var(--ink-2);list-style:none;padding:0">' + req + '</ul>' : '') +
      '<h4>Visible answer (first 900 characters)</h4><div class="ans" id="ansText">Loading…</div>';
    openSheet();
    loadTexts().then(function (T) { var el = $('ansText'); if (el) el.textContent = T[a[0] + '|' + a[1] + '|' + a[2] + '|' + a[3]] || '(no text recorded)'; })
      .catch(function () { var el = $('ansText'); if (el) el.textContent = 'Could not load the answer text.'; });
  }
  var textsP = null;
  function loadTexts() { if (!textsP) textsP = fetch('answers.json?v=1').then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); return textsP; }
  $('swarmChart').addEventListener('click', function (ev) { var t = ev.target.closest('[data-i]'); if (t) { hideTip(); openAnswer(+t.getAttribute('data-i')); } });
  $('swarmChart').addEventListener('keydown', function (ev) { var t = ev.target.closest('[data-i]'); if (t && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); openAnswer(+t.getAttribute('data-i')); } });

  /* ---------- sheets ---------- */
  var sheet = $('sheet'), lastFocus = null;
  function openSheet() { lastFocus = document.activeElement; if (sheet.showModal) sheet.showModal(); else sheet.setAttribute('open', ''); }
  function closeD(d) { if (d.close) d.close(); else d.removeAttribute('open'); if (lastFocus && lastFocus.focus) lastFocus.focus(); }
  $('sheetClose').addEventListener('click', function () { closeD(sheet); });
  sheet.addEventListener('click', function (ev) { if (ev.target === sheet) closeD(sheet); });
  var lb = $('lightbox');
  $('lbClose').addEventListener('click', function () { closeD(lb); });
  lb.addEventListener('click', function (ev) { if (ev.target === lb) closeD(lb); });

  /* ---------- refusals ---------- */
  function renderRefusals() {
    $('corrTpl').textContent = D.correction.config.template.replace('{twin}', '<neutral twin>');
    $('refGrid').innerHTML = FAM.map(function (f) {
      return '<div class="ref-card"><h3>' + f.name + '</h3>' + [f.std, f.abl].map(function (mod) {
        var rows = D.answers.filter(function (a) { return a[0] === mod; });
        var full = rows.filter(function (a) { return a[6] === 'full_refusal'; }).length, part = rows.filter(function (a) { return a[6] === 'partial_refusal'; }).length;
        var cells = ''; for (var i = 0; i < rows.length; i++) cells += '<i class="' + (i < full ? 'f' : i < full + part ? 'p' : '') + '"></i>';
        var v = variantOf(mod);
        return '<div class="ref-line ' + (v === 'std' ? 'a' : 'b') + '"><span>' + (v === 'std' ? 'Standard' : 'Abliterated') + '</span><div class="waffle" role="img" aria-label="' + full + ' full and ' + part + ' partial refusals of ' + rows.length + '">' + cells + '</div><b>' + (full + part) + '/' + rows.length + '</b></div>';
      }).join('') + '<p class="ref-key">One square per answer (both wordings, all 6 runs). Solid: full refusal. Light: partial.</p></div>';
    }).join('');
    $('corrList').innerHTML = D.corrections.map(function (c, i) {
      var f = famOf[c.model];
      return '<button class="corr" data-c="' + i + '"><b>' + c.prompt_id + ' · run ' + c.run + '</b> <span class="muted" style="font-size:13px">' + f.name + ' standard</span>' +
        '<p>Turn 1 judged: ' + (refusalName[c.parent_refusal_type] || c.parent_refusal_type) + '. Then: “' + esc(c.correction_text) + '”</p>' +
        '<div class="toks">turn 1 ' + n0(c.turn1_input_tokens + c.turn1_output_tokens) + ' tok → turn 2 ' + n0(c.input_tokens + c.output_tokens) + ' tok</div></button>';
    }).join('');
  }
  $('corrList').addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-c]'); if (!b) return;
    var c = D.corrections[+b.getAttribute('data-c')], f = famOf[c.model];
    $('sheetKicker').textContent = f.name + ' standard · ' + c.prompt_id + ' · run ' + c.run + ' · not judged yet';
    $('sheetTitle').textContent = PROMPTS[c.prompt_id].prompt;
    $('sheetBody').innerHTML = '<h4>Turn 1 (judged ' + esc(refusalName[c.parent_refusal_type] || c.parent_refusal_type) + ') &middot; ' + n0(c.turn1_input_tokens) + ' in, ' + n0(c.turn1_output_tokens) + ' out</h4><div class="ans"></div>' +
      '<h4>User follow-up</h4><div class="ans"></div><h4>Turn 2 &middot; ' + n0(c.input_tokens) + ' in (whole conversation), ' + n0(c.output_tokens) + ' out &middot; not judged</h4><div class="ans"></div>';
    var boxes = $('sheetBody').querySelectorAll('.ans');
    boxes[0].textContent = c.turn1_excerpt || '(no text)'; boxes[1].textContent = c.correction_text; boxes[2].textContent = c.excerpt;
    openSheet();
  });

  /* ---------- capability ---------- */
  function renderCap() {
    var el = $('capChart'), W = width(el), narrow = W < 600;
    var ml = narrow ? 64 : 200, mr = narrow ? 58 : 80, rowH = 30, gap = 22, top = 10;
    var mets = [['accuracy', 'Overall'], ['accuracy_gsm8k', 'GSM8K'], ['accuracy_mmlu', 'MMLU']];
    var H = top + FAM.length * (mets.length * rowH + gap) + 26;
    var lo = 0.5, hi = 1;
    function X(v) { return ml + (v - lo) / (hi - lo) * (W - ml - mr); }
    var g = '';
    [0.5, 0.6, 0.7, 0.8, 0.9, 1].forEach(function (t) { g += '<g class="grid"><line x1="' + X(t) + '" x2="' + X(t) + '" y1="' + top + '" y2="' + (H - 24) + '"/></g><text x="' + X(t) + '" y="' + (H - 6) + '" text-anchor="middle" font-size="12">' + Math.round(t * 100) + '%</text>'; });
    var y = top;
    FAM.forEach(function (f) {
      var S = D.capability.per_model[f.std], A = D.capability.per_model[f.abl];
      g += '<text x="0" y="' + (y + rowH / 2 + 4) + '" font-size="' + (narrow ? 12 : 14) + '" style="fill:var(--ink);font-weight:600">' + (narrow ? f.name.split(' ')[0] : f.name) + '</text>';
      mets.forEach(function (mt, j) {
        var yy = y + j * rowH + rowH / 2, s = S[mt[0]], a = A[mt[0]], d = (a - s) * 100;
        g += '<text x="' + (ml - 10) + '" y="' + (yy + 4) + '" text-anchor="end" font-size="12">' + (narrow && j === 0 ? '' : mt[1]) + '</text>';
        if (narrow && j === 0) g += '';
        g += '<line x1="' + X(s) + '" x2="' + X(a) + '" y1="' + yy + '" y2="' + yy + '" style="stroke:var(--ink-3);stroke-width:2"/>';
        g += '<circle class="mk" cx="' + X(s) + '" cy="' + yy + '" r="6" style="fill:var(--series-a);stroke:var(--bg);stroke-width:2" data-tip="1" data-t="' + f.name + ' standard|' + mt[1] + '|' + s + '"/>';
        g += '<circle class="mk" cx="' + X(a) + '" cy="' + yy + '" r="6" style="fill:var(--series-b);stroke:var(--bg);stroke-width:2" data-tip="1" data-t="' + f.name + ' abliterated|' + mt[1] + '|' + a + '"/>';
        g += '<text x="' + (W - 2) + '" y="' + (yy + 4) + '" text-anchor="end" font-size="12" style="fill:var(--ink);font-variant-numeric:tabular-nums">' + (d > 0 ? '+' : d < 0 ? '−' : '') + Math.abs(d).toFixed(1) + ' pts</text>';
      });
      y += mets.length * rowH + gap;
    });
    el.innerHTML = '<div class="legend"><span><i class="dot a"></i>Standard</span><span><i class="dot b"></i>Abliterated</span><span class="muted">Right: change in points</span></div>' + svgEl(W, H, g, 'Capability accuracy, standard vs abliterated');
  }
  bindTips($('capChart'), function (t) { var p = t.getAttribute('data-t').split('|'); return '<b>' + esc(p[0]) + '</b><br>' + p[1] + ': ' + (p[2] * 100).toFixed(1) + '%'; });

  /* ---------- blocking ---------- */
  function renderBlock() {
    $('blockMsg').textContent = D.block.block_message;
    $('blockGrid').innerHTML = D.prompts.map(function (p) {
      var b = D.block.per_prompt[p.id], t = b.original_matched_term, txt = esc(p.prompt);
      if (b.original_blocked && t) {
        var i = p.prompt.toLowerCase().indexOf(t.toLowerCase());
        if (i >= 0) txt = esc(p.prompt.slice(0, i)) + '<s>' + esc(p.prompt.slice(i, i + t.length)) + '</s>' + esc(p.prompt.slice(i + t.length));
      }
      return '<div class="blk' + (b.original_blocked ? '' : ' pass') + '"><span class="id">' + p.id + '</span><div><div class="orig">' + txt + '</div>' +
        (b.original_blocked ? '<div class="twin">' + esc(p.neutral_twin) + '</div><div class="st">Blocked on “' + esc(t) + '”: 0 model tokens, then answered from the twin</div>'
                            : '<div class="st">No block-list word: goes straight to the model</div>') + '</div></div>';
    }).join('') + '<p class="p2-note" style="grid-column:1/-1">Original blocked: ' + D.block.n_original_blocked + ' of ' + D.block.n_prompts + '. Twin blocked: ' + D.block.n_twin_blocked + ' of ' + D.block.n_prompts + '. Block list: ' + D.block_list.map(esc).join(', ') + '.</p>';
  }

  /* ---------- trust ---------- */
  function renderTrust() {
    var V = D.verify, c = { PASS: 0, WARN: 0, FAIL: 0 }; V.items.forEach(function (it) { c[it.level] = (c[it.level] || 0) + 1; });
    var tot = V.items.length, areas = {};
    V.items.forEach(function (it) { areas[it.area] = (areas[it.area] || 0) + 1; });
    var nonPass = V.items.filter(function (it) { return it.level !== 'PASS'; });
    $('verifyCard').innerHTML = '<h3>Verifier report</h3><p>' + c.PASS + ' checks passed, ' + c.WARN + ' warning, ' + c.FAIL + ' failed. It recomputes the summary from the raw answer files, checks every model’s weights against its pinned digest, and confirms the seeds and settings.</p>' +
      '<div class="vbar" role="img" aria-label="' + c.PASS + ' pass, ' + c.WARN + ' warn, ' + c.FAIL + ' fail"><i style="flex:' + c.PASS + ';background:var(--series-a)"></i><i style="flex:' + c.WARN + ';background:var(--series-b)"></i>' + (c.FAIL ? '<i style="flex:' + c.FAIL + ';background:var(--ink)"></i>' : '') + '</div>' +
      '<ul class="vlist">' + nonPass.map(function (it) { return '<li><b style="color:var(--warn-ink)">' + it.level + '</b><span>' + esc(it.message) + '</span></li>'; }).join('') +
      Object.keys(areas).map(function (a) { return '<li><b>' + areas[a] + '</b><span>' + esc(a) + ' checks</span></li>'; }).join('') + '</ul>' +
      '<p style="margin-top:12px">Judge used for all ' + D.judge.judged + ' first-pass judgments: <code>' + esc(D.judge.judge_models_used[0].repo) + '</code> at <code>' + esc(D.judge.judge_models_used[0].revision.slice(0, 12)) + '</code>. That version is no longer on the run server.</p>';
    var T = [
      ['m', '06:30 UTC · M1', 'The Mac reviewer opens the channel. 42 of 720 answers done, verifier at 0 FAIL.'],
      ['h', '06:40 UTC · H1', 'The run agent replies: Qwen standard is generating at about 21 seconds per answer. It flags a stray second copy of one model’s weights on the server and leaves it for the user.'],
      ['m', '08:30 UTC · M2', 'Two archive snapshots show 2 FAIL. The reviewer suspects a timing race: Llama answers land between the analysis and the check.'],
      ['h', '08:33 UTC · H2', 'Re-run back to back: 0 FAIL. Llama standard is complete, and the run continues.'],
      ['stop', '10:22 UTC · H3', '<b>Run stopped.</b> The judge’s pinned weights are gone from the server, and two new copies appeared just as the first judge pass began. All answers, capability items and first-pass judgments were complete. The 8 correction turns are not judged.'],
      ['m', '10:30 UTC · M3', 'Passed to the user. No workarounds from either agent.'],
      ['m', '15:45 UTC · M4', 'The user chose to <b>diagnose first</b>: no re-pin, no re-judge, nothing deleted until then.']
    ];
    $('timeline').innerHTML = T.map(function (t) { return '<li class="' + t[0] + '"><span class="when">7 Nov 2026 · ' + t[1] + '</span>' + t[2] + '</li>'; }).join('') +
      '<li class="h" style="padding-bottom:0"><span class="when">Key</span>H = run agent on the lab server (hopper), M = reviewer on the Mac. Paraphrased from <code>comms/</code>.</li>';
  }

  /* ---------- gallery ---------- */
  var FIGS = [['family_ratios', 'Within-family ratios'], ['per_prompt_tokens', 'Per-prompt tokens'], ['token_distribution', 'Token distribution'], ['thinking_split', 'Thinking split'], ['refusal_heatmap', 'Refusal heatmap'], ['capability', 'Capability'], ['correction_gap', 'Correction gap'], ['correction_per_prompt', 'Correction per prompt'], ['progress', 'Run progress']];
  function renderGallery() {
    $('gallery').innerHTML = FIGS.map(function (f) { return '<button data-f="' + f[0] + '" data-t="' + f[1] + '"><img loading="lazy" src="fig/' + f[0] + '.png?v=1" alt="' + f[1] + ' figure from the pilot repo"><span>' + f[1] + '</span></button>'; }).join('');
  }
  $('gallery').addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-f]'); if (!b) return;
    $('lbImg').src = 'fig/' + b.getAttribute('data-f') + '.png?v=1'; $('lbImg').alt = b.getAttribute('data-t'); $('lbTitle').textContent = b.getAttribute('data-t');
    lastFocus = b; if (lb.showModal) lb.showModal(); else lb.setAttribute('open', '');
  });

  /* ---------- footer ---------- */
  $('foot').innerHTML = '<p>Source: <a href="https://github.com/SummerPandey/Fun-Project-2.0">SummerPandey/Fun-Project-2.0</a>, commit <code>52c21f9</code>. Numbers come from <code>pilot/results/summary.json</code>, <code>per_prompt.csv</code>, the answer and judgment logs, and <code>verify_report.json</code> (summary generated ' + esc(D.generated_at.replace('T', ' ').replace('+00:00', ' UTC')) + '). Mock data: ' + (D.mock ? 'yes' : 'no') + '.</p>' +
    '<p>Answer excerpts are the models’ own visible text, cut to 900 characters. This page is a snapshot and does not update when the repo changes.</p><p><a href="../">Back to the proposal</a></p>';

  /* ---------- render loop ---------- */
  function render(key) {
    if (!key || key === 'runset' || key === 'cond') { renderFamilies(); renderRatios(); }
    if (!key || key === 'ppfam' || key === 'ppword') renderPP();
    if (!key || key === 'swword' || key === 'swrun') renderSwarm();
  }
  renderTiles(); renderObs(); renderRefusals(); renderCap(); renderBlock(); renderTrust(); renderGallery(); render();
  var lastW = window.innerWidth, rt;
  window.addEventListener('resize', function () {
    if (window.innerWidth === lastW) return; lastW = window.innerWidth;
    clearTimeout(rt); rt = setTimeout(function () { $('ppChart').innerHTML = ''; renderRatios(); renderPP(); renderSwarm(); renderCap(); }, 120);
  });
  if (reduced) document.documentElement.classList.add('reduced');
})();
