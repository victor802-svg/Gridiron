/* Gridiron front end. Vanilla JS, no build step, no framework.
 *
 * LAW 4 lives in here too, not only on the server: `requireN` throws if
 * anything is about to be drawn without its sample size. A page that renders a
 * probability with no N beside it is a page that lies by omission, so the
 * renderer would rather fail loudly than draw it.
 */
'use strict';

const Gridiron = (function () {

  // --- LAW 4 -------------------------------------------------------------
  class MissingSampleSize extends Error {}

  function requireN(obj, where) {
    if (!obj || typeof obj.n !== 'number') {
      throw new MissingSampleSize(
        'LAW 4: refusing to render ' + where + ' without its sample size. ' +
        'No calibration curve, edge estimate or factor verdict renders ' +
        'without its N beside it.'
      );
    }
    return obj.n;
  }

  // --- formatting --------------------------------------------------------
  const pct = (x, dp) => (x === null || x === undefined) ? '—' : (x * 100).toFixed(dp === undefined ? 1 : dp) + '%';
  const num = (x, dp) => (x === null || x === undefined) ? '—' : Number(x).toFixed(dp === undefined ? 4 : dp);
  const int = (x) => (x === null || x === undefined) ? '—' : Number(x).toLocaleString();
  const signed = (x, dp) => (x === null || x === undefined) ? '—' : (x > 0 ? '+' : '') + Number(x).toFixed(dp === undefined ? 1 : dp);

  function nTag(n) {
    const s = document.createElement('span');
    s.className = 'n-tag';
    s.textContent = ' n=' + int(n);
    return s;
  }

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }

  function table(host, columns, rows) {
    host.innerHTML = '';
    const thead = el('thead');
    const hr = el('tr');
    columns.forEach(c => hr.appendChild(el('th', c.cls || '', c.label)));
    thead.appendChild(hr);
    host.appendChild(thead);
    const tbody = el('tbody');
    rows.forEach(r => {
      const tr = el('tr');
      r.forEach((cell, i) => {
        const td = el('td', columns[i].cls || '');
        if (cell instanceof Node) td.appendChild(cell); else td.textContent = cell;
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    host.appendChild(tbody);
  }

  // --- data --------------------------------------------------------------
  const state = { meta: null, scorecard: null, historyOffset: 0, historyTotal: 0 };

  async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (e) { /* body was not json */ }
      throw new Error(url + ' → ' + res.status + ': ' + detail);
    }
    return res.json();
  }

  function showError(err) {
    const box = document.getElementById('error');
    box.hidden = false;
    box.textContent = String(err && err.message ? err.message : err);
  }

  function clearError() {
    document.getElementById('error').hidden = true;
  }

  // --- the calibration chart ---------------------------------------------
  const AXIS_MIN = 0.40, AXIS_MAX = 1.0;

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#000';
  }

  function drawCalibration(canvas, curveData) {
    const buckets = curveData.buckets || [];
    buckets.forEach((b, i) => requireN(b, 'calibration bucket ' + (b.label || i)));

    const dpr = window.devicePixelRatio || 1;
    const W = canvas.width, H = canvas.height;
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);

    const pad = { l: 62, r: 20, t: 18, b: 52 };
    const w = W - pad.l - pad.r, h = H - pad.t - pad.b;
    const X = v => pad.l + (v - AXIS_MIN) / (AXIS_MAX - AXIS_MIN) * w;
    const Y = v => pad.t + h - (v - AXIS_MIN) / (AXIS_MAX - AXIS_MIN) * h;

    const ink = css('--ink'), faint = css('--ink-faint'), rule = css('--rule');
    ctx.font = '11px ui-sans-serif, system-ui, sans-serif';
    ctx.textBaseline = 'middle';

    // grid
    ctx.strokeStyle = rule; ctx.lineWidth = 1;
    for (let v = AXIS_MIN; v <= AXIS_MAX + 1e-9; v += 0.1) {
      ctx.beginPath(); ctx.moveTo(X(v), pad.t); ctx.lineTo(X(v), pad.t + h); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(pad.l, Y(v)); ctx.lineTo(pad.l + w, Y(v)); ctx.stroke();
      ctx.fillStyle = faint; ctx.textAlign = 'center';
      ctx.fillText(Math.round(v * 100) + '%', X(v), pad.t + h + 16);
      ctx.textAlign = 'right';
      ctx.fillText(Math.round(v * 100) + '%', pad.l - 8, Y(v));
    }

    // the diagonal: where a perfectly calibrated forecaster sits
    ctx.strokeStyle = faint; ctx.setLineDash([5, 4]); ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(X(AXIS_MIN), Y(AXIS_MIN)); ctx.lineTo(X(AXIS_MAX), Y(AXIS_MAX)); ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = faint; ctx.textAlign = 'center';
    ctx.fillText('claimed confidence', pad.l + w / 2, H - 14);
    ctx.save();
    ctx.translate(16, pad.t + h / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText('actually happened', 0, 0);
    ctx.restore();
    ctx.textAlign = 'right';
    ctx.fillStyle = faint;
    ctx.fillText('dashed line = perfect calibration', pad.l + w, pad.t + 8);

    const drawn = buckets.filter(b => b.n > 0 && b.claimed !== null);
    if (!drawn.length) {
      ctx.fillStyle = ink; ctx.textAlign = 'center'; ctx.font = '13px ui-sans-serif, sans-serif';
      ctx.fillText('Nothing has resolved yet in this category.', pad.l + w / 2, pad.t + h / 2);
      return;
    }

    const model = css('--model');
    // 95% interval on the observed rate. A four-sample bucket should look as
    // uncertain as it is.
    drawn.forEach(b => {
      const se = Math.sqrt(Math.max(b.actual * (1 - b.actual), 1e-6) / b.n);
      const lo = Math.max(AXIS_MIN, b.actual - 1.96 * se);
      const hi = Math.min(AXIS_MAX, b.actual + 1.96 * se);
      ctx.strokeStyle = model; ctx.globalAlpha = 0.35; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(X(b.claimed), Y(lo)); ctx.lineTo(X(b.claimed), Y(hi)); ctx.stroke();
      ctx.globalAlpha = 1;
    });

    ctx.strokeStyle = model; ctx.lineWidth = 2; ctx.beginPath();
    drawn.forEach((b, i) => {
      const x = X(b.claimed), y = Y(Math.min(Math.max(b.actual, AXIS_MIN), AXIS_MAX));
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();

    drawn.forEach(b => {
      const x = X(b.claimed), y = Y(Math.min(Math.max(b.actual, AXIS_MIN), AXIS_MAX));
      ctx.fillStyle = model;
      ctx.beginPath();
      ctx.arc(x, y, b.provisional ? 3.5 : 5.5, 0, Math.PI * 2);
      ctx.fill();
      if (b.provisional) {
        ctx.strokeStyle = css('--bg'); ctx.lineWidth = 1.5; ctx.stroke();
      }
      // LAW 4: N is printed on every point, always.
      ctx.fillStyle = ink; ctx.textAlign = 'left'; ctx.font = '11px ui-sans-serif, sans-serif';
      ctx.fillText('n=' + b.n, x + 9, y - 9);
    });
  }

  // --- TRACK RECORD ------------------------------------------------------
  function findCurve(scorecard, market, predictor) {
    return (scorecard.categories || []).find(c =>
      c.filters.market_type === market && c.filters.predictor === predictor);
  }

  function renderRecord() {
    const sc = state.scorecard;
    const market = document.getElementById('chart-market').value;
    const predictor = document.getElementById('chart-predictor').value;
    const curve = findCurve(sc, market, predictor) || sc.headline;
    requireN(curve, 'calibration curve');

    const head = document.getElementById('record-headline');
    head.innerHTML = '';
    head.appendChild(el('div', '', curve.largest_gap));
    head.appendChild(el('div', 'sub',
      'Showing ' + market + ' / ' + predictor + '. ' + int(curve.n) +
      ' resolved predictions in this category. The sentence above always names ' +
      'the largest gap, never the best-looking bucket.'));

    document.getElementById('chart-caption').textContent =
      '— ' + market + ' / ' + predictor + ', n=' + int(curve.n);
    drawCalibration(document.getElementById('calibration'), curve);

    table(document.getElementById('bucket-table'),
      [{ label: 'Confidence bucket' }, { label: 'N' }, { label: 'Claimed' },
       { label: 'Actual' }, { label: 'Gap' }, { label: '' }],
      curve.buckets.map(b => {
        requireN(b, 'bucket row ' + b.label);
        return [
          b.label, int(b.n), pct(b.claimed), pct(b.actual),
          b.gap === null ? '—' : signed(b.gap * 100, 1) + ' pts',
          b.n === 0 ? 'no predictions yet'
            : (b.provisional ? 'provisional: below ' + state.meta.minimum_for_bucket_point : '')
        ];
      }));

    renderScores(sc, curve, market, predictor);
    renderEdge(sc.edge);
    document.getElementById('separation-note').textContent = sc.separation_note;
  }

  function scoreCard(title, payload, extraNote) {
    const n = requireN(payload, 'score card "' + title + '"');
    const card = el('div', 'score-card');
    const h = el('h3', '', title);
    h.appendChild(nTag(n));
    card.appendChild(h);
    if (n === 0) {
      card.appendChild(el('div', 'score-row', 'Nothing resolved yet.'));
      return card;
    }
    [['Brier', num(payload.brier)], ['Log loss', num(payload.log_loss)],
     ['Hit rate', pct(payload.hit_rate)]].forEach(([k, v]) => {
      if (v === '—') return;
      const row = el('div', 'score-row');
      row.appendChild(el('span', 'label', k));
      row.appendChild(el('span', 'stat-value', v));
      card.appendChild(row);
    });
    if (extraNote) card.appendChild(el('div', 'footnote', extraNote));
    return card;
  }

  function renderScores(sc, curve, market, predictor) {
    const host = document.getElementById('record-scores');
    host.innerHTML = '';
    const h = el('h2', '', 'Scores');
    h.appendChild(el('span', 'caption', ' — lower Brier and log loss are better'));
    host.appendChild(h);

    const grid = el('div', 'scores');
    grid.appendChild(scoreCard('Model: ' + market + ' / ' + predictor, curve.score));
    grid.appendChild(scoreCard('Baseline: always 50%', curve.baselines.always_50,
      curve.baselines.always_50.note));
    grid.appendChild(scoreCard('Baseline: the market', curve.baselines.market,
      curve.baselines.market.note));
    if (curve.baselines.model_on_market_subset) {
      grid.appendChild(scoreCard('Model, same questions as the market',
        curve.baselines.model_on_market_subset,
        'Restricted to the questions the market priced, so the comparison is like for like.'));
    }
    host.appendChild(grid);

    const byCat = el('div');
    byCat.appendChild(el('h2', '', 'Record by category'));
    byCat.appendChild(el('p', 'caption',
      'Kept separate. Averaging a fast easy category with a slow hard one flatters the model.'));
    const t = el('table', 'grid');
    table(t,
      [{ label: 'Category' }, { label: 'N' }, { label: 'Brier' },
       { label: 'Log loss' }, { label: 'Hit rate' }],
      sc.categories.map(c => {
        requireN(c.score, 'category ' + c.category);
        return [c.category, int(c.score.n), num(c.score.brier),
                num(c.score.log_loss), pct(c.score.hit_rate)];
      }));
    byCat.appendChild(t);
    host.appendChild(byCat);
  }

  function renderEdge(edge) {
    const host = document.getElementById('record-edge');
    host.innerHTML = '';
    const h = el('h2', '', 'The edge question');
    h.appendChild(el('span', 'caption',
      ' — where the model disagreed with the market, who was right?'));
    host.appendChild(h);

    if (!edge.renderable) {
      const box = el('div', 'empty');
      box.appendChild(el('div', '', edge.message));
      box.appendChild(el('div', 'footnote', edge.standing_note));
      host.appendChild(box);
      return;
    }

    const t = el('table', 'grid');
    const rows = [edge.model_more_confident, edge.market_more_confident].map(side => {
      requireN(side, 'edge side "' + side.label + '"');
      return [side.label, int(side.n), pct(side.mean_model_prob),
              pct(side.mean_market_prob), pct(side.resolved_in_model_favour)];
    });
    table(t, [{ label: 'Disagreement' }, { label: 'N' }, { label: 'Model said' },
              { label: 'Market said' }, { label: 'Resolved model’s way' }], rows);
    host.appendChild(t);
    host.appendChild(el('p', 'footnote', edge.standing_note));
  }

  // --- THIS WEEK ---------------------------------------------------------
  function probBlock(kind, label, value, note) {
    const d = el('div', 'prob ' + kind);
    d.appendChild(el('span', 'k', label));
    d.appendChild(el('span', 'v', value));
    if (note) d.appendChild(el('span', 'note', note));
    return d;
  }

  function renderCard(c) {
    const card = el('div', 'card');
    const head = el('div', 'card-head');
    const left = el('div');
    left.appendChild(el('div', 'card-claim', c.claim || (c.subject + ' ' + signed(c.line_asked))));
    left.appendChild(el('div', 'card-meta',
      c.matchup + ' · ' + c.market_type + ' · ' + c.predictor +
      ' · asked at ' + signed(c.line_asked) +
      ' · written ' + (c.created_utc || '').replace('T', ' ') +
      ' · factor set ' + c.factor_set_version));
    head.appendChild(left);

    const right = el('div');
    if (c.outcome !== null && c.outcome !== undefined) {
      right.appendChild(el('span', 'tag ' + (c.outcome ? 'win' : 'loss'),
        c.outcome ? 'resolved: correct' : 'resolved: wrong'));
    }
    if (c.degraded) right.appendChild(el('span', 'tag warn', c.degraded));
    head.appendChild(right);
    card.appendChild(head);

    const probs = el('div', 'probs');
    probs.appendChild(probBlock('model', 'model says', pct(c.model_prob),
      c.model_side.replace('_', ' ')));
    if (c.market_implied_prob !== null && c.market_implied_prob !== undefined) {
      probs.appendChild(probBlock('market', 'market implies', pct(c.market_implied_prob),
        'line ' + signed(c.market_line)));
      const cls = c.gap >= 0 ? 'gap-pos' : 'gap-neg';
      probs.appendChild(probBlock(cls, 'disagreement', signed(c.gap * 100, 1) + ' pts',
        c.gap >= 0 ? 'model more confident' : 'market more confident'));
    } else {
      probs.appendChild(probBlock('market', 'market implies', '—',
        'no free line source'));
    }
    probs.appendChild(probBlock('', 'public %', '—', 'no free source; never proxied'));
    card.appendChild(probs);

    if (c.top_factors && c.top_factors.length) {
      const ul = el('ul', 'factor-list');
      c.top_factors.forEach(f => {
        const li = el('li');
        const name = el('span', 'fname', f.factor);
        if (f.missing) name.appendChild(el('span', 'tag warn', 'defaulted'));
        li.appendChild(name);
        li.appendChild(el('span', 'fval', num(f.value, 3)));
        li.appendChild(el('span', 'fcon',
          f.contribution === null || f.contribution === undefined
            ? '' : signed(f.contribution, 3)));
        li.appendChild(el('span', 'fwhy', f.rationale));
        ul.appendChild(li);
      });
      card.appendChild(ul);
    }

    if (c.reasoning) card.appendChild(el('div', 'reasoning', c.reasoning));
    (c.notes || []).forEach(nte => card.appendChild(el('div', 'footnote', 'Note: ' + nte)));
    return card;
  }

  async function renderWeek() {
    const picker = document.getElementById('week-picker');
    const chosen = picker.value ? JSON.parse(picker.value) : {};
    const qs = chosen.season ? ('?season=' + chosen.season + '&week=' + chosen.week) : '';
    const data = await fetchJSON('/api/week' + qs);

    document.getElementById('week-title').textContent =
      data.week === null ? 'This week' : ('Season ' + data.season + ', week ' + data.week);
    document.getElementById('week-sort').textContent =
      data.n + ' forecasts · sorted by ' + (data.sorted_by || '');

    const host = document.getElementById('week-cards');
    host.innerHTML = '';
    if (!data.cards.length) {
      host.appendChild(el('div', 'empty',
        data.message || 'No forecasts recorded for this week yet.'));
      return;
    }
    data.cards.forEach(c => host.appendChild(renderCard(c)));
  }

  async function loadWeekPicker() {
    const data = await fetchJSON('/api/weeks');
    const picker = document.getElementById('week-picker');
    picker.innerHTML = '';
    data.weeks.forEach(w => {
      const o = el('option', '', w.season + ' week ' + w.week + ' (' + w.n + ')');
      o.value = JSON.stringify({ season: w.season, week: w.week });
      picker.appendChild(o);
    });
  }

  // --- FACTORS -----------------------------------------------------------
  async function renderFactors() {
    const data = await fetchJSON('/api/factors');
    requireN(data, 'factor report');
    document.getElementById('factors-caption').textContent =
      '— scored over ' + int(data.n) + ' resolved statistical predictions';
    document.getElementById('factors-method').textContent = data.method;

    table(document.getElementById('factors-table'),
      [{ label: 'Factor' }, { label: 'Added' }, { label: 'Applies to' },
       { label: 'N' }, { label: 'Brier' }, { label: 'Δ Brier' },
       { label: 'Mean |effect|' }, { label: 'Verdict' }, { label: 'Why it was declared', cls: 'wide' }],
      data.factors.map(f => {
        requireN(f, 'factor row ' + f.factor);
        const name = el('span', '', f.factor);
        if (!f.active) name.appendChild(el('span', 'tag warn', 'inactive'));
        return [
          name, (f.added_utc || '').slice(0, 10), f.applies_to.join(', '),
          int(f.n), num(f.brier), f.delta_brier === null ? '—' : signed(f.delta_brier, 5),
          num(f.mean_abs_contribution, 4), f.verdict,
          f.note ? f.rationale + ' — NOTE: ' + f.note : f.rationale
        ];
      }));
  }

  // --- VERSIONS ----------------------------------------------------------
  async function renderVersions() {
    const data = await fetchJSON('/api/versions');
    requireN(data, 'version comparison');
    document.getElementById('versions-caption').textContent =
      '— current: ' + data.current;
    document.getElementById('versions-note').textContent = data.note;

    const host = document.getElementById('versions-list');
    host.innerHTML = '';
    data.versions.forEach(v => {
      const card = el('div', 'score-card');
      const h = el('h3', '', v.version + '  ');
      h.appendChild(el('span', 'tag' + (v.status === 'current' ? '' : ' warn'), v.status));
      h.appendChild(nTag(v.n));
      card.appendChild(h);
      card.appendChild(el('div', 'card-meta',
        'activated ' + (v.activated_utc || 'unrecorded') +
        ' · ' + int(v.predictions_written) + ' written · ' +
        int(v.open) + ' open'));

      if (v.message) {
        card.appendChild(el('div', 'empty', v.message));
      } else {
        const t = el('table', 'grid');
        table(t, [{ label: 'Category' }, { label: 'N' }, { label: 'Brier' },
                  { label: 'Log loss' }, { label: 'Hit rate' }],
          v.categories.map(c => {
            requireN(c, 'version ' + v.version + ' / ' + c.category);
            return [c.category, int(c.n), num(c.brier), num(c.log_loss), pct(c.hit_rate)];
          }));
        card.appendChild(t);
      }
      host.appendChild(card);
    });

    // There is deliberately no total row. Summing a closed record and an
    // accumulating one would describe neither model.
    host.appendChild(el('p', 'footnote',
      'No combined total is shown, and none will be: these are different ' +
      'forecasters, and their sum describes nobody.'));
  }

  // --- HISTORY -----------------------------------------------------------
  function historyQuery() {
    const p = new URLSearchParams();
    const q = document.getElementById('history-q').value.trim();
    if (q) p.set('q', q);
    const m = document.getElementById('history-market').value;
    if (m) p.set('market_type', m);
    const pr = document.getElementById('history-predictor').value;
    if (pr) p.set('predictor', pr);
    const o = document.getElementById('history-outcome').value;
    if (o) p.set('outcome', o);
    p.set('limit', '100');
    p.set('offset', String(state.historyOffset));
    return p.toString();
  }

  async function renderHistory() {
    const data = await fetchJSON('/api/history?' + historyQuery());
    requireN(data, 'history');
    state.historyTotal = data.n;
    document.getElementById('history-caption').textContent =
      '— ' + int(data.n) + ' predictions match';

    table(document.getElementById('history-table'),
      [{ label: 'Written' }, { label: 'Season/wk' }, { label: 'Subject' },
       { label: 'Market' }, { label: 'By' }, { label: 'Asked' },
       { label: 'Model' }, { label: 'Line then' }, { label: 'Market' },
       { label: 'Outcome' }],
      data.items.map(i => {
        let outcome = 'open';
        if (i.outcome === 1) outcome = 'correct';
        else if (i.outcome === 0) outcome = 'wrong';
        return [
          (i.created_utc || '').slice(0, 10), i.season + ' wk' + i.week,
          i.subject, i.market_type, i.predictor, signed(i.line_asked),
          pct(i.model_prob), i.market_line_at_the_time === null ? '—' : signed(i.market_line_at_the_time),
          pct(i.market_implied_prob), outcome
        ];
      }));

    const from = data.n ? state.historyOffset + 1 : 0;
    document.getElementById('history-range').textContent =
      from + '–' + (state.historyOffset + data.returned) + ' of ' + int(data.n);
    document.getElementById('history-prev').disabled = state.historyOffset === 0;
    document.getElementById('history-next').disabled =
      state.historyOffset + data.returned >= data.n;
  }

  // --- chrome ------------------------------------------------------------
  function renderBanner(meta) {
    const banner = document.getElementById('kind-banner');
    if (meta.database_kind === 'live') { banner.hidden = true; return; }
    banner.hidden = false;
    banner.innerHTML = '';
    banner.appendChild(el('strong', '', meta.database_kind.toUpperCase() + ' DATABASE — '));
    banner.appendChild(document.createTextNode(meta.database_note || ''));
  }

  function renderColophon(meta) {
    const parts = [
      'Factor set ' + meta.factor_set_version,
      int(meta.predictions) + ' predictions on record',
      int(meta.games_final) + ' completed games loaded (' +
        meta.seasons_loaded[0] + '–' + meta.seasons_loaded[1] + ')',
      'market comparison available for ' + int(meta.market_coverage.with_market_line) +
        ' of ' + int(meta.market_coverage.n),
      'LLM spend today $' + Number(meta.llm_ledger.usd_spent).toFixed(4) +
        ' of $' + Number(meta.llm_ledger.usd_cap).toFixed(2)
    ];
    document.getElementById('colophon-text').textContent = parts.join(' · ');
  }

  const ROUTES = {
    record: renderRecord,
    week: renderWeek,
    factors: renderFactors,
    versions: renderVersions,
    history: renderHistory
  };

  async function route() {
    clearError();
    const name = (location.hash.replace('#/', '') || 'record');
    const view = ROUTES[name] ? name : 'record';
    document.querySelectorAll('.view').forEach(v => { v.hidden = true; });
    document.getElementById('view-' + view).hidden = false;
    document.querySelectorAll('nav a').forEach(a => {
      a.classList.toggle('active', a.dataset.route === view);
    });
    try {
      await ROUTES[view]();
    } catch (err) {
      showError(err);
    }
  }

  async function boot() {
    try {
      state.meta = await fetchJSON('/api/meta');
      renderBanner(state.meta);
      renderColophon(state.meta);
      state.scorecard = await fetchJSON('/api/scorecard');
      await loadWeekPicker();
    } catch (err) {
      showError(err);
    }

    window.addEventListener('hashchange', route);
    ['chart-market', 'chart-predictor'].forEach(id =>
      document.getElementById(id).addEventListener('change', () => {
        try { renderRecord(); } catch (err) { showError(err); }
      }));
    document.getElementById('week-picker').addEventListener('change', () =>
      renderWeek().catch(showError));
    ['history-q', 'history-market', 'history-predictor', 'history-outcome'].forEach(id =>
      document.getElementById(id).addEventListener('input', () => {
        state.historyOffset = 0;
        renderHistory().catch(showError);
      }));
    document.getElementById('history-prev').addEventListener('click', () => {
      state.historyOffset = Math.max(0, state.historyOffset - 100);
      renderHistory().catch(showError);
    });
    document.getElementById('history-next').addEventListener('click', () => {
      state.historyOffset += 100;
      renderHistory().catch(showError);
    });

    await route();
    document.body.dataset.ready = 'true';
  }

  return { boot, route, state, requireN, MissingSampleSize, drawCalibration, fetchJSON };
})();

window.Gridiron = Gridiron;
document.addEventListener('DOMContentLoaded', () => { Gridiron.boot(); });
