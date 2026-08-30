/* Gridiron front end. Vanilla JS, no build step, no framework.
 *
 * LAW 4 lives here too, not only on the server: `requireN` throws if anything
 * is about to be drawn without its sample size, and every visual goes through
 * it — the calibration chart, the weekly strip, the bucket chip on a pick card.
 * A page that renders a probability with no N beside it lies by omission, so
 * the renderer would rather fail loudly than draw it.
 *
 * Design rules enforced in code, not only in the stylesheet:
 *   - the dumbbell tells model from market by FORM (filled vs hollow), never by
 *     hue, because colour is reserved for the value of the gap between them;
 *   - contribution bars are signed, sorted by magnitude, capped at five;
 *   - nothing animates except card expansion.
 */
'use strict';

const Gridiron = (function () {

  // --- LAW 4 -------------------------------------------------------------
  class MissingSampleSize extends Error {}

  function requireN(obj, where) {
    if (!obj || typeof obj.n !== 'number') {
      throw new MissingSampleSize(
        'LAW 4: refusing to render ' + where + ' without its sample size. ' +
        'No calibration curve, edge estimate, chart or factor verdict renders ' +
        'without its N beside it.'
      );
    }
    return obj.n;
  }

  // --- formatting --------------------------------------------------------
  const DASH = '—';
  const pct = (x, dp) => (x === null || x === undefined) ? DASH : (x * 100).toFixed(dp === undefined ? 1 : dp) + '%';
  const num = (x, dp) => (x === null || x === undefined) ? DASH : Number(x).toFixed(dp === undefined ? 4 : dp);
  const int = (x) => (x === null || x === undefined) ? DASH : Number(x).toLocaleString();
  const signed = (x, dp) => (x === null || x === undefined) ? DASH : (x > 0 ? '+' : '') + Number(x).toFixed(dp === undefined ? 1 : dp);

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }

  function nTag(n) { return el('span', 'n-tag', ' n=' + int(n)); }

  function table(host, columns, rows) {
    host.innerHTML = '';
    const thead = el('thead'), hr = el('tr');
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

  function skeleton(host, cls, count) {
    host.innerHTML = '';
    for (let i = 0; i < (count || 1); i++) host.appendChild(el('div', 'skeleton ' + cls));
  }

  // --- data --------------------------------------------------------------
  // `sport` is the outermost piece of state on the page. Every fetch carries
  // it, because every number below belongs to exactly one sport (LAW 6).
  const state = { sport: 'nfl', sports: [], meta: null, scorecard: null,
                  markets: ['spread'], historyOffset: 0, historyTotal: 0 };

  function withSport(path, extra) {
    const p = new URLSearchParams(extra || {});
    p.set('sport', state.sport);
    return path + (path.includes('?') ? '&' : '?') + p.toString();
  }

  async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (e) { /* not json */ }
      throw new Error(url + ' → ' + res.status + ': ' + detail);
    }
    return res.json();
  }

  function showError(err) {
    const box = document.getElementById('error');
    box.hidden = false;
    box.textContent = String(err && err.message ? err.message : err);
  }
  function clearError() { document.getElementById('error').hidden = true; }

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#000';
  }

  function prepareCanvas(canvas, ctx) {
    const dpr = window.devicePixelRatio || 1;
    const W = Number(canvas.getAttribute('width'));
    const H = Number(canvas.getAttribute('height'));
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    return { W, H };
  }

  // --- the calibration chart ---------------------------------------------
  const AXIS_MIN = 0.40, AXIS_MAX = 1.0;
  // How far from the diagonal still reads as well calibrated. Drawn as a band
  // so a reader can see at a glance whether a miss is really a miss.
  const ACCEPTABLE = 0.05;

  function drawCalibration(canvas, curveData) {
    const buckets = (curveData && curveData.buckets) || [];
    buckets.forEach((b, i) => requireN(b, 'calibration bucket ' + (b.label || i)));

    const ctx = canvas.getContext('2d');
    const dims = prepareCanvas(canvas, ctx);
    const W = dims.W, H = dims.H;
    const pad = { l: 56, r: 18, t: 16, b: 46 };
    const w = W - pad.l - pad.r, h = H - pad.t - pad.b;
    const X = v => pad.l + (v - AXIS_MIN) / (AXIS_MAX - AXIS_MIN) * w;
    const Y = v => pad.t + h - (v - AXIS_MIN) / (AXIS_MAX - AXIS_MIN) * h;
    const clamp = v => Math.min(Math.max(v, AXIS_MIN), AXIS_MAX);

    const ink = css('--ink'), faint = css('--ink-3'), rule = css('--rule');
    ctx.font = '12px ui-sans-serif, system-ui, sans-serif';
    ctx.textBaseline = 'middle';

    ctx.fillStyle = css('--band');
    ctx.beginPath();
    ctx.moveTo(X(AXIS_MIN), Y(clamp(AXIS_MIN + ACCEPTABLE)));
    ctx.lineTo(X(AXIS_MAX), Y(clamp(AXIS_MAX)));
    ctx.lineTo(X(AXIS_MAX), Y(clamp(AXIS_MAX - ACCEPTABLE)));
    ctx.lineTo(X(AXIS_MIN), Y(clamp(AXIS_MIN)));
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = rule; ctx.lineWidth = 1;
    for (let v = AXIS_MIN; v <= AXIS_MAX + 1e-9; v += 0.1) {
      ctx.beginPath(); ctx.moveTo(X(v), pad.t); ctx.lineTo(X(v), pad.t + h); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(pad.l, Y(v)); ctx.lineTo(pad.l + w, Y(v)); ctx.stroke();
      ctx.fillStyle = faint;
      ctx.textAlign = 'center'; ctx.fillText(Math.round(v * 100) + '%', X(v), pad.t + h + 15);
      ctx.textAlign = 'right'; ctx.fillText(Math.round(v * 100) + '%', pad.l - 8, Y(v));
    }

    ctx.strokeStyle = faint; ctx.setLineDash([5, 4]); ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(X(AXIS_MIN), Y(AXIS_MIN)); ctx.lineTo(X(AXIS_MAX), Y(AXIS_MAX));
    ctx.stroke(); ctx.setLineDash([]);

    ctx.fillStyle = faint; ctx.textAlign = 'center';
    ctx.fillText('claimed confidence', pad.l + w / 2, H - 12);
    ctx.save();
    ctx.translate(14, pad.t + h / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText('actually happened', 0, 0);
    ctx.restore();
    ctx.textAlign = 'right';
    ctx.fillText('dashed = perfect  ·  shaded = within ' +
      Math.round(ACCEPTABLE * 100) + ' points', pad.l + w, pad.t + 7);

    const drawn = buckets.filter(b => b.n > 0 && b.claimed !== null);
    if (!drawn.length) {
      ctx.fillStyle = ink; ctx.textAlign = 'center';
      ctx.fillText('Nothing has resolved yet in this category.', pad.l + w / 2, pad.t + h / 2);
      return;
    }

    ctx.strokeStyle = ink; ctx.lineWidth = 1.25;
    drawn.forEach(b => {
      const se = Math.sqrt(Math.max(b.actual * (1 - b.actual), 1e-6) / b.n);
      ctx.globalAlpha = 0.32;
      ctx.beginPath();
      ctx.moveTo(X(b.claimed), Y(clamp(b.actual - 1.96 * se)));
      ctx.lineTo(X(b.claimed), Y(clamp(b.actual + 1.96 * se)));
      ctx.stroke();
      ctx.globalAlpha = 1;
    });

    drawn.forEach(b => {
      const x = X(b.claimed), y = Y(clamp(b.actual));
      ctx.fillStyle = ink;
      ctx.beginPath(); ctx.arc(x, y, b.provisional ? 3.5 : 5.5, 0, Math.PI * 2); ctx.fill();
      if (b.provisional) { ctx.strokeStyle = css('--card'); ctx.lineWidth = 1.5; ctx.stroke(); }
      ctx.fillStyle = ink; ctx.textAlign = 'left';
      ctx.fillText('n=' + b.n, x + 9, y - 10);          // LAW 4, on every point
    });
  }

  // --- the weekly strip ---------------------------------------------------
  function drawOverTime(canvas, data) {
    requireN(data, 'calibration-over-time strip');
    const points = data.points || [];
    points.forEach((p, i) => requireN(p, 'weekly point ' + (p.label || i)));

    const ctx = canvas.getContext('2d');
    const dims = prepareCanvas(canvas, ctx);
    const W = dims.W, H = dims.H;
    const pad = { l: 56, r: 18, t: 14, b: 26 };
    const w = W - pad.l - pad.r, h = H - pad.t - pad.b;
    const ink = css('--ink'), faint = css('--ink-3'), rule = css('--rule');
    ctx.font = '12px ui-sans-serif, system-ui, sans-serif';
    ctx.textBaseline = 'middle';
    canvas._hits = [];

    if (!points.length) {
      ctx.fillStyle = faint; ctx.textAlign = 'center';
      ctx.fillText('No resolved weeks yet.', W / 2, H / 2);
      return;
    }

    const span = Math.max(0.25, Math.max.apply(null, points.map(p => Math.abs(p.gap))) * 1.25);
    const X = i => pad.l + (points.length === 1 ? w / 2 : (i / (points.length - 1)) * w);
    const Y = g => pad.t + h / 2 - (g / span) * (h / 2);

    ctx.strokeStyle = rule; ctx.lineWidth = 1;
    [-span / 2, 0, span / 2].forEach(g => {
      ctx.beginPath(); ctx.moveTo(pad.l, Y(g)); ctx.lineTo(pad.l + w, Y(g)); ctx.stroke();
      ctx.fillStyle = faint; ctx.textAlign = 'right';
      ctx.fillText(signed(g * 100, 0) + ' pts', pad.l - 8, Y(g));
    });
    ctx.strokeStyle = faint; ctx.setLineDash([4, 3]);
    ctx.beginPath(); ctx.moveTo(pad.l, Y(0)); ctx.lineTo(pad.l + w, Y(0)); ctx.stroke();
    ctx.setLineDash([]);

    points.forEach((p, i) => {
      const x = X(i), y = Y(p.gap);
      ctx.strokeStyle = rule; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, Y(0)); ctx.lineTo(x, y); ctx.stroke();
      ctx.fillStyle = p.gap >= 0 ? css('--pos') : css('--neg');
      ctx.beginPath(); ctx.arc(x, y, p.provisional ? 2.5 : 4, 0, Math.PI * 2); ctx.fill();
      canvas._hits.push({ x: x, y: y, point: p });
    });

    ctx.fillStyle = faint; ctx.textAlign = 'left';
    ctx.fillText(points[0].label, pad.l, pad.t + h + 12);
    ctx.textAlign = 'right';
    ctx.fillText(points[points.length - 1].label, pad.l + w, pad.t + h + 12);
    ctx.textAlign = 'center'; ctx.fillStyle = ink;
    ctx.fillText('actual minus claimed, by week  ·  hover for N',
      pad.l + w / 2, pad.t + h + 12);
  }

  function attachStripTooltip(canvas) {
    if (canvas._tooltipBound) return;
    canvas._tooltipBound = true;
    const tip = document.getElementById('tooltip');
    canvas.addEventListener('mousemove', ev => {
      const rect = canvas.getBoundingClientRect();
      const x = ev.clientX - rect.left, y = ev.clientY - rect.top;
      let best = null, bestD = 16;
      (canvas._hits || []).forEach(hit => {
        const d = Math.sqrt((hit.x - x) * (hit.x - x) + (hit.y - y) * (hit.y - y));
        if (d < bestD) { bestD = d; best = hit; }
      });
      if (!best) { tip.hidden = true; return; }
      const p = best.point;
      tip.hidden = false;
      tip.textContent =
        p.label + '\nn=' + int(p.n) + '  (running ' + int(p.cumulative_n) + ')' +
        '\nclaimed ' + pct(p.claimed) + ', actual ' + pct(p.actual) +
        '\ngap ' + signed(p.gap * 100, 1) + ' pts';
      tip.style.left = (ev.clientX + 14) + 'px';
      tip.style.top = (ev.clientY + 14) + 'px';
    });
    canvas.addEventListener('mouseleave', () => { tip.hidden = true; });
  }

  // --- TRACK RECORD ------------------------------------------------------
  function findCurve(scorecard, market, predictor) {
    return (scorecard.categories || []).find(c =>
      c.market === market && c.filters.predictor === predictor);
  }

  function renderRecord() {
    const sc = state.scorecard;
    const market = document.getElementById('chart-market').value || 'spread';
    const predictor = document.getElementById('chart-predictor').value || 'statistical';
    const curve = findCurve(sc, market, predictor) || sc.headline;
    requireN(curve, 'calibration curve');

    const head = document.getElementById('record-headline');
    head.innerHTML = '';
    head.appendChild(el('div', '', curve.largest_gap));
    head.appendChild(el('div', 'sub',
      market + ' / ' + predictor + '. ' + int(curve.n) + ' resolved' +
      (curve.voided ? ', ' + int(curve.voided) + ' void' : '') +
      '. The sentence above always names the largest gap, never the best bucket.'));

    document.getElementById('chart-caption').textContent =
      DASH + ' ' + market + ' / ' + predictor + ', n=' + int(curve.n);
    drawCalibration(document.getElementById('calibration'), curve);
    document.getElementById('largest-gap-prose').textContent = curve.largest_gap;

    table(document.getElementById('bucket-table'),
      [{ label: 'Confidence bucket' }, { label: 'N' }, { label: 'Claimed' },
       { label: 'Actual' }, { label: 'Gap' }, { label: '' }],
      curve.buckets.map(b => {
        requireN(b, 'bucket row ' + b.label);
        return [
          b.label, int(b.n), pct(b.claimed), pct(b.actual),
          b.gap === null ? DASH : signed(b.gap * 100, 1) + ' pts',
          b.n === 0 ? 'no predictions yet'
            : (b.provisional ? 'provisional: below ' + state.meta.minimum_for_bucket_point : '')
        ];
      }));

    renderScores(sc, curve, market, predictor);
    renderEdge(sc.edge);
    document.getElementById('separation-note').textContent = sc.separation_note;
    renderOverTime(market, predictor).catch(showError);
  }

  async function renderOverTime(market, predictor) {
    const params = new URLSearchParams({ predictor: predictor });
    if (market === 'spread') params.set('market_type', 'spread');
    else { params.set('market_type', 'prop'); params.set('prop_type', market); }
    const data = await fetchJSON(withSport('/api/over-time?' + params.toString()));
    document.getElementById('overtime-caption').textContent =
      DASH + ' ' + int(data.n) + ' resolved across ' + int(data.points.length) + ' weeks';
    document.getElementById('overtime-note').textContent = data.note;
    const canvas = document.getElementById('overtime');
    drawOverTime(canvas, data);
    attachStripTooltip(canvas);
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
     ['Hit rate', pct(payload.hit_rate)]].forEach(pair => {
      if (pair[1] === DASH) return;
      const row = el('div', 'score-row');
      row.appendChild(el('span', 'label', pair[0]));
      row.appendChild(el('span', 'stat-value', pair[1]));
      card.appendChild(row);
    });
    if (extraNote) card.appendChild(el('div', 'footnote', extraNote));
    return card;
  }

  function renderScores(sc, curve, market, predictor) {
    const host = document.getElementById('record-scores');
    host.innerHTML = '';
    const h = el('h2', '', 'Scores');
    h.appendChild(el('span', 'caption', ' ' + DASH + ' lower Brier and log loss are better'));
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
      'Never merged. Each market is its own question with its own difficulty.'));
    const wrap = el('div', 'table-scroll');
    const t = el('table', 'grid');
    table(t,
      [{ label: 'Category' }, { label: 'N' }, { label: 'Void' }, { label: 'Brier' },
       { label: 'Log loss' }, { label: 'Hit rate' }],
      sc.categories.map(c => {
        requireN(c.score, 'category ' + c.category);
        return [c.category, int(c.score.n), int(c.voided), num(c.score.brier),
                num(c.score.log_loss), pct(c.score.hit_rate)];
      }));
    wrap.appendChild(t);
    byCat.appendChild(wrap);
    host.appendChild(byCat);
  }

  function renderEdge(edge) {
    const host = document.getElementById('record-edge');
    host.innerHTML = '';
    const h = el('h2', '', 'The edge question');
    h.appendChild(el('span', 'caption',
      ' ' + DASH + ' where the model disagreed with the market, who was right?'));
    host.appendChild(h);

    if (!edge.renderable) {
      const box = el('div', 'empty');
      box.appendChild(el('div', '', edge.message));
      box.appendChild(el('div', 'footnote', edge.standing_note));
      host.appendChild(box);
      return;
    }
    const wrap = el('div', 'table-scroll');
    const t = el('table', 'grid');
    table(t, [{ label: 'Disagreement' }, { label: 'N' }, { label: 'Model said' },
              { label: 'Market said' }, { label: 'Resolved model’s way' }],
      [edge.model_more_confident, edge.market_more_confident].map(side => {
        requireN(side, 'edge side "' + side.label + '"');
        return [side.label, int(side.n), pct(side.mean_model_prob),
                pct(side.mean_market_prob), pct(side.resolved_in_model_favour)];
      }));
    wrap.appendChild(t);
    host.appendChild(wrap);
    host.appendChild(el('p', 'footnote', edge.standing_note));
  }

  // --- THE PICK CARD ------------------------------------------------------

  /* Two dots on one 0-100 rail with the gap shaded between them, so "how far
     apart, and which way" is one glance rather than two percentages and a
     subtraction. */
  function dumbbell(card) {
    const wrap = el('div', 'dumbbell');
    const rail = el('div', 'rail');
    rail.appendChild(el('div', 'rail-line'));

    const model = card.model_prob;
    const market = card.market_implied_prob;
    const at = v => (v * 100) + '%';
    const hasMarket = market !== null && market !== undefined;

    // Where no line source exists, the rail is NOT drawn against an invented
    // number. The absence is stated and the model's own probability stands on
    // its own. A missing source degrades the comparison, never the record.
    if (!hasMarket) {
      const bare = el('div', 'dumbbell');
      const block = el('div', 'rail-legend');
      const m = el('div');
      m.appendChild(el('span', 'k', 'MODEL'));
      m.appendChild(el('div', 'v', pct(model)));
      m.appendChild(el('span', 'chip-sub', card.model_side.replace('_', ' ')));
      block.appendChild(m);
      const none = el('div');
      none.appendChild(el('span', 'k', 'MARKET'));
      none.appendChild(el('div', 'v no-line', 'no line available'));
      none.appendChild(el('span', 'chip-sub',
        (card.line_availability && card.line_availability.reason)
          ? card.line_availability.reason.split('.')[0] + '.'
          : 'no free source prices this market'));
      block.appendChild(none);
      bare.appendChild(block);
      return bare;
    }

    if (hasMarket) {
      const span = el('div', 'rail-span ' + (model >= market ? 'pos' : 'neg'));
      span.style.left = at(Math.min(model, market));
      span.style.width = (Math.abs(model - market) * 100) + '%';
      rail.appendChild(span);
      const marketDot = el('div', 'rail-dot market');
      marketDot.style.left = at(market);
      marketDot.title = 'market implies ' + pct(market);
      rail.appendChild(marketDot);
    }
    const modelDot = el('div', 'rail-dot model');
    modelDot.style.left = at(model);
    modelDot.title = 'model says ' + pct(model);
    rail.appendChild(modelDot);
    wrap.appendChild(rail);

    const scale = el('div', 'rail-scale');
    ['0%', '50%', '100%'].forEach(t => scale.appendChild(el('span', '', t)));
    wrap.appendChild(scale);

    const legend = el('div', 'rail-legend');
    const modelBlock = el('div');
    modelBlock.appendChild(el('span', 'k', 'MODEL ●'));
    modelBlock.appendChild(el('div', 'v', pct(model)));
    legend.appendChild(modelBlock);

    const marketBlock = el('div');
    marketBlock.appendChild(el('span', 'k', 'MARKET ○'));
    marketBlock.appendChild(el('div', 'v', hasMarket ? pct(market) : DASH));
    if (!hasMarket) marketBlock.appendChild(el('span', 'chip-sub', 'no free line source'));
    legend.appendChild(marketBlock);

    if (card.gap !== null && card.gap !== undefined) {
      const gapBlock = el('div');
      gapBlock.appendChild(el('span', 'k', 'GAP'));
      gapBlock.appendChild(el('div', 'v gap-value ' + (card.gap >= 0 ? 'pos' : 'neg'),
        signed(card.gap * 100, 1) + ' pts'));
      gapBlock.appendChild(el('span', 'chip-sub',
        card.gap >= 0 ? 'model more confident' : 'market more confident'));
      legend.appendChild(gapBlock);
    }
    wrap.appendChild(legend);
    return wrap;
  }

  /* Signed contribution bars: which factors pushed toward the model's side and
     which pushed away. The reasoning, made visible. */
  function contributions(card) {
    const rows = (card.top_factors || []).filter(f =>
      f.contribution !== null && f.contribution !== undefined);
    if (!rows.length) return null;

    const host = el('div', 'contrib');
    const scale = Math.max(Math.max.apply(null, rows.map(f => Math.abs(f.contribution))), 0.01);

    function bar(f) {
      const row = el('div', 'contrib-row');
      row.appendChild(el('div', 'contrib-name', f.factor));
      const track = el('div', 'contrib-track');
      const b = el('div', 'contrib-bar ' + (f.contribution >= 0 ? 'pos' : 'neg'));
      const half = Math.abs(f.contribution) / scale * 50;
      if (f.contribution >= 0) { b.style.left = '50%'; b.style.width = half + '%'; }
      else { b.style.left = (50 - half) + '%'; b.style.width = half + '%'; }
      b.title = f.rationale || '';
      track.appendChild(b);
      row.appendChild(track);
      row.appendChild(el('div', 'contrib-value', signed(f.contribution, 3)));
      return row;
    }

    rows.slice(0, 5).forEach(f => host.appendChild(bar(f)));
    const rest = rows.slice(5);
    if (rest.length) {
      const hidden = el('div');
      hidden.hidden = true;
      rest.forEach(f => hidden.appendChild(bar(f)));
      const more = el('button', 'contrib-more', '+ ' + rest.length + ' more factors');
      more.addEventListener('click', ev => {
        ev.stopPropagation();
        hidden.hidden = !hidden.hidden;
        more.textContent = hidden.hidden
          ? '+ ' + rest.length + ' more factors' : 'show fewer';
      });
      host.appendChild(hidden);
      host.appendChild(more);
    }
    return host;
  }

  /* This pick's confidence bucket, with that bucket's live accuracy and N.
     Never the accuracy without the N: the chip sits beside a specific forecast
     and reads as a track record for THAT pick. */
  function bucketChip(bucket) {
    requireN(bucket, 'bucket chip');
    const chip = el('span', 'chip' + (bucket.provisional ? ' provisional' : ''));
    chip.appendChild(el('span', 'chip-label', bucket.label));
    if (bucket.n === 0) {
      chip.appendChild(el('span', 'chip-sub', 'no record yet · n=0'));
    } else {
      chip.appendChild(el('span', '', pct(bucket.actual) + ' actual'));
      chip.appendChild(el('span', 'chip-sub', 'n=' + int(bucket.n) +
        (bucket.provisional ? ' · provisional' : '')));
    }
    return chip;
  }

  function outcomeStamp(card) {
    if (card.voided) return el('span', 'outcome-stamp void', 'void');
    if (card.outcome === 1) return el('span', 'outcome-stamp win', 'correct');
    if (card.outcome === 0) return el('span', 'outcome-stamp loss', 'wrong');
    return null;
  }

  function renderCard(c) {
    const card = el('div', 'card');

    const head = el('div', 'card-head');
    head.setAttribute('role', 'button');
    head.setAttribute('tabindex', '0');
    const left = el('div');
    left.appendChild(el('div', 'card-claim',
      c.claim || (c.subject + ' ' + signed(c.line_asked))));
    left.appendChild(el('div', 'card-meta',
      c.matchup + ' · ' + c.market + ' · ' + c.predictor +
      ' · asked at ' + signed(c.line_asked) + ' · ' + c.factor_set_version));
    head.appendChild(left);

    const right = el('div');
    right.appendChild(bucketChip(c.bucket));
    const stamp = outcomeStamp(c);
    if (stamp) right.appendChild(stamp);
    if (c.degraded) right.appendChild(el('span', 'tag warn', c.degraded));
    head.appendChild(right);
    card.appendChild(head);

    const body = el('div', 'card-body');
    body.appendChild(dumbbell(c));
    const bars = contributions(c);
    if (bars) body.appendChild(bars);
    card.appendChild(body);

    const detail = el('div', 'card-detail');
    const inner = el('div', 'card-detail-inner');
    if (c.reasoning) inner.appendChild(el('div', 'reasoning', c.reasoning));

    const wrap = el('div', 'table-scroll');
    const t = el('table', 'grid');
    table(t, [{ label: 'Factor' }, { label: 'Value' }, { label: 'Contribution' },
              { label: 'Source' }, { label: 'Why it is declared', cls: 'wide' }],
      (c.top_factors || []).map(f => [
        f.factor,
        (f.value === null || f.value === undefined) ? 'not measurable' : num(f.value, 3),
        (f.contribution === null || f.contribution === undefined)
          ? DASH : signed(f.contribution, 3),
        f.source || DASH,
        f.rationale || ''
      ]));
    wrap.appendChild(t);
    inner.appendChild(wrap);

    if ((c.absent_factors || []).length) {
      inner.appendChild(el('h3', '', 'Not measurable for this game'));
      inner.appendChild(el('div', 'footnote',
        c.absent_factors.map(a => a.factor + ' (' + a.why + ')').join('; ')));
    }

    inner.appendChild(el('div', 'footnote',
      'Prediction written ' + (c.created_utc || '?').replace('T', ' ') +
      (c.market_fetched_utc
        ? ' · market snapshot taken ' + c.market_fetched_utc.replace('T', ' ') +
          ' from ' + (c.market_source || 'unknown')
        : ' · no market snapshot') +
      ((c.market_line !== null && c.market_line !== undefined)
        ? ' · line at the time ' + signed(c.market_line) : '') +
      ' · factor coverage ' +
      ((c.factor_coverage === null || c.factor_coverage === undefined)
        ? 'not recorded' : pct(c.factor_coverage, 0))));

    if (c.void_reason) inner.appendChild(el('div', 'footnote', 'VOID: ' + c.void_reason));
    (c.notes || []).forEach(n => inner.appendChild(el('div', 'footnote', 'Note: ' + n)));

    detail.appendChild(inner);
    card.appendChild(detail);

    function toggle() { card.classList.toggle('open'); }
    head.addEventListener('click', toggle);
    head.addEventListener('keydown', ev => {
      if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggle(); }
    });
    return card;
  }

  // --- THIS WEEK ----------------------------------------------------------
  async function renderWeek() {
    const host = document.getElementById('week-cards');
    skeleton(host, 'skeleton-card', 3);

    const picker = document.getElementById('week-picker');
    const chosen = picker.value ? JSON.parse(picker.value) : {};
    const qs = chosen.season ? ('?season=' + chosen.season + '&week=' + chosen.week) : '';
    const data = await fetchJSON(withSport('/api/week' + qs));
    const market = document.getElementById('week-market').value;

    document.getElementById('week-title').textContent =
      data.week === null ? 'This week' : ('Season ' + data.season + ', week ' + data.week);
    document.getElementById('week-sort').textContent =
      data.n + ' forecasts · sorted by ' + (data.sorted_by || '');

    host.innerHTML = '';
    const cards = market ? data.cards.filter(c => c.market === market) : data.cards;
    if (!cards.length) {
      host.appendChild(el('div', 'empty', data.message ||
        (market ? 'No ' + market + ' forecasts on this slate.'
                : 'No forecasts recorded for this week yet.')));
      return;
    }
    cards.forEach(c => host.appendChild(renderCard(c)));
  }

  async function loadWeekPicker() {
    const data = await fetchJSON(withSport('/api/weeks'));
    const picker = document.getElementById('week-picker');
    picker.innerHTML = '';
    data.weeks.forEach(w => {
      const o = el('option', '', w.season + ' week ' + w.week + ' (' + w.n + ')');
      o.value = JSON.stringify({ season: w.season, week: w.week });
      picker.appendChild(o);
    });
  }

  async function loadMarkets() {
    const data = await fetchJSON(withSport('/api/markets'));
    state.markets = data.spread.concat(data.props);
    const chart = document.getElementById('chart-market');
    chart.innerHTML = '';
    state.markets.forEach(m => {
      const o = el('option', '', m); o.value = m; chart.appendChild(o);
    });
    ['week-market', 'history-market'].forEach(id => {
      const sel = document.getElementById(id);
      state.markets.forEach(m => {
        const o = el('option', '', m); o.value = m; sel.appendChild(o);
      });
    });
  }

  // --- VERSIONS -----------------------------------------------------------
  async function renderVersions() {
    const data = await fetchJSON(withSport('/api/versions'));
    requireN(data, 'version comparison');
    document.getElementById('versions-caption').textContent = DASH + ' current: ' + data.current;
    document.getElementById('versions-note').textContent = data.note;

    const host = document.getElementById('versions-list');
    host.innerHTML = '';
    const grid = el('div', 'scores');
    data.versions.forEach(v => {
      const card = el('div', 'score-card');
      const h = el('h3', '', v.version + ' ');
      h.appendChild(el('span', 'tag' + (v.status === 'current' ? '' : ' warn'), v.status));
      h.appendChild(nTag(v.n));
      card.appendChild(h);
      card.appendChild(el('div', 'card-meta',
        'activated ' + (v.activated_utc || 'unrecorded').slice(0, 10) +
        ' · ' + int(v.predictions_written) + ' written · ' +
        int(v.open) + ' open'));
      if (v.message) {
        card.appendChild(el('div', 'empty', v.message));
      } else {
        const wrap = el('div', 'table-scroll');
        const t = el('table', 'grid');
        table(t, [{ label: 'Category' }, { label: 'N' }, { label: 'Brier' },
                  { label: 'Hit rate' }],
          v.categories.filter(c => c.n > 0).map(c => {
            requireN(c, 'version ' + v.version + ' / ' + c.category);
            return [c.category, int(c.n), num(c.brier), pct(c.hit_rate)];
          }));
        wrap.appendChild(t);
        card.appendChild(wrap);
      }
      grid.appendChild(card);
    });
    host.appendChild(grid);
    host.appendChild(el('p', 'footnote',
      'No combined total is shown, and none will be: these are different ' +
      'forecasters, and their sum describes nobody.'));
  }

  // --- FACTORS ------------------------------------------------------------
  async function renderFactors() {
    const data = await fetchJSON(withSport('/api/factors'));
    requireN(data, 'factor report');
    document.getElementById('factors-caption').textContent =
      DASH + ' scored over ' + int(data.n) + ' resolved statistical predictions';
    document.getElementById('factors-method').textContent = data.method;

    table(document.getElementById('factors-table'),
      [{ label: 'Factor' }, { label: 'Added' }, { label: 'Applies to' },
       { label: 'N' }, { label: 'Rows measured' }, { label: 'Δ Brier' },
       { label: 'Mean |effect|' }, { label: 'Verdict' },
       { label: 'Why it was declared', cls: 'wide' }],
      data.factors.map(f => {
        requireN(f, 'factor row ' + f.factor);
        const name = el('span', '', f.factor);
        if (!f.active) name.appendChild(el('span', 'tag warn', 'inactive'));
        return [
          name, (f.added_utc || '').slice(0, 10), f.applies_to.join(', '),
          int(f.n), int(f.training_rows_measured),
          (f.delta_brier === null || f.delta_brier === undefined)
            ? DASH : signed(f.delta_brier, 5),
          num(f.mean_abs_contribution, 4), f.verdict,
          f.note ? f.rationale + ' — NOTE: ' + f.note : f.rationale
        ];
      }));
  }

  // --- HISTORY ------------------------------------------------------------
  function historyQuery() {
    const p = new URLSearchParams();
    const q = document.getElementById('history-q').value.trim();
    if (q) p.set('q', q);
    const m = document.getElementById('history-market').value;
    if (m === 'spread') p.set('market_type', 'spread');
    else if (m) p.set('prop_type', m);
    const pr = document.getElementById('history-predictor').value;
    if (pr) p.set('predictor', pr);
    const o = document.getElementById('history-outcome').value;
    if (o) p.set('outcome', o);
    p.set('limit', '100');
    p.set('offset', String(state.historyOffset));
    return p.toString();
  }

  async function renderHistory() {
    const data = await fetchJSON(withSport('/api/history?' + historyQuery()));
    requireN(data, 'history');
    state.historyTotal = data.n;
    document.getElementById('history-caption').textContent =
      DASH + ' ' + int(data.n) + ' predictions match';

    table(document.getElementById('history-table'),
      [{ label: 'Written' }, { label: 'Season/wk' }, { label: 'Subject' },
       { label: 'Market' }, { label: 'By' }, { label: 'Asked' },
       { label: 'Model' }, { label: 'Line then' }, { label: 'Market' },
       { label: 'Outcome' }],
      data.items.map(i => {
        let outcome = 'open';
        if (i.voided) outcome = 'void';
        else if (i.outcome === 1) outcome = 'correct';
        else if (i.outcome === 0) outcome = 'wrong';
        return [
          (i.created_utc || '').slice(0, 10), i.season + ' wk' + i.week,
          i.subject, i.market, i.predictor, signed(i.line_asked),
          pct(i.model_prob),
          i.market_line_at_the_time === null ? DASH : signed(i.market_line_at_the_time),
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

  // --- sport tabs ---------------------------------------------------------
  async function loadSports() {
    const data = await fetchJSON('/api/sports');
    state.sports = data.sports;
    const host = document.getElementById('sport-tabs');
    host.innerHTML = '';
    data.sports.forEach(sp => {
      const b = el('button', '', sp.label);
      // LAW 4 in the navigation: the count is on the label, so an empty record
      // is visible before the tab is clicked rather than after.
      b.appendChild(el('span', 'tab-n', 'n=' + int(sp.n)));
      b.setAttribute('aria-current', sp.sport === state.sport ? 'true' : 'false');
      b.dataset.sport = sp.sport;
      b.addEventListener('click', () => selectSport(sp.sport));
      host.appendChild(b);
    });
    document.getElementById('sport-note').textContent = data.never_summed;
  }

  async function selectSport(sport) {
    if (sport === state.sport) return;
    state.sport = sport;
    state.historyOffset = 0;
    document.querySelectorAll('#sport-tabs button').forEach(b => {
      b.setAttribute('aria-current', b.dataset.sport === sport ? 'true' : 'false');
    });
    try {
      state.meta = await fetchJSON(withSport('/api/meta'));
      renderBanner(state.meta);
      renderColophon(state.meta);
      state.scorecard = await fetchJSON(withSport('/api/scorecard'));
      await loadMarkets();
      await loadWeekPicker();
      await route();
    } catch (err) {
      showError(err);
    }
  }

  // --- chrome -------------------------------------------------------------
  function renderBanner(meta) {
    const banner = document.getElementById('kind-banner');
    if (meta.database_kind === 'live') { banner.hidden = true; return; }
    banner.hidden = false;
    banner.innerHTML = '';
    banner.appendChild(el('strong', '', meta.database_kind.toUpperCase() + ' DATABASE — '));
    banner.appendChild(document.createTextNode(meta.database_note || ''));
  }

  function renderColophon(meta) {
    document.getElementById('colophon-text').textContent = [
      'Factor set ' + meta.factor_set_version,
      int(meta.predictions) + ' predictions on record',
      int(meta.games_final) + ' completed games loaded (' +
        meta.seasons_loaded[0] + '–' + meta.seasons_loaded[1] + ')',
      'market comparison for ' + int(meta.market_coverage.with_market_line) +
        ' of ' + int(meta.market_coverage.n),
      'LLM spend today $' + Number(meta.llm_ledger.usd_spent).toFixed(4) +
        ' of $' + Number(meta.llm_ledger.usd_cap).toFixed(2)
    ].join(' · ');
  }

  // --- the schedule panel -------------------------------------------------
  // Honest about failure, never reassuring. A task that has not run is not
  // rendered as a blank row: it says it has never run, and says what that
  // means. The one thing this panel must never do is look calm when the
  // appliance has stopped.
  async function renderSchedule() {
    const data = await fetchJSON('/api/schedule');
    const host = document.getElementById('schedule-tasks');
    host.innerHTML = '';

    const caption = document.getElementById('schedule-caption');
    const problems = data.tasks.filter(t => t.silent).length;
    const missed = data.tasks.reduce((n, t) => n + t.missed.length, 0);
    caption.textContent = problems || missed
      ? problems + ' quiet · ' + missed + ' missed'
      : 'all tasks reporting';
    caption.className = 'caption' + (problems || missed ? ' warn' : '');

    data.tasks.forEach(t => {
      const card = el('div', 'sched' + (t.silent ? ' sched-warn' : ''));
      const head = el('div', 'sched-head');
      head.appendChild(el('strong', '', t.task));
      head.appendChild(el('span', 'sched-result ' + 'r-' + (t.last_result || 'never'),
                          t.last_result || 'never run'));
      card.appendChild(head);
      card.appendChild(el('div', 'sched-what', t.what));

      const rows = [
        ['last ran', t.last_run_utc ? t.last_run_utc.replace('T', ' ') +
          '  (' + t.age_hours + 'h ago)' : 'never'],
        ['next due', t.next_due_utc ? t.next_due_utc.replace('T', ' ') : 'unknown'],
        ['every', t.every_hours + 'h'],
        ['failures all time', String(t.failures_all_time)]
      ];
      const dl = el('div', 'sched-grid');
      rows.forEach(([k, v]) => {
        dl.appendChild(el('span', 'sched-k', k));
        dl.appendChild(el('span', 'sched-v', v));
      });
      card.appendChild(dl);

      if (t.last_detail) card.appendChild(el('div', 'sched-detail', t.last_detail));
      (t.degraded || []).forEach(d => {
        card.appendChild(el('div', 'sched-alarm',
          'ran degraded: ' + d + ' — the statistical forecaster stood alone'));
      });
      if (t.warning) card.appendChild(el('div', 'sched-alarm', t.warning));
      t.missed.forEach(m => {
        card.appendChild(el('div', 'sched-missed',
          'MISSED ' + m.started_utc.replace('T', ' ') + ' — ' + m.detail));
      });
      host.appendChild(card);
    });

    const stale = document.getElementById('schedule-staleness');
    stale.innerHTML = '';
    data.schedule_staleness.sports.forEach(s => {
      const row = el('div', 'sched-stale' + (s.stale ? ' sched-warn' : ''));
      row.appendChild(el('strong', '', s.label));
      row.appendChild(el('span', 'sched-detail', s.note));
      stale.appendChild(row);
    });
  }

  const ROUTES = {
    record: renderRecord,
    week: renderWeek,
    factors: renderFactors,
    versions: renderVersions,
    history: renderHistory,
    schedule: renderSchedule
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
    try { await ROUTES[view](); } catch (err) { showError(err); }
  }

  // The app shell is cached so the app opens instantly and survives a flaky
  // connection. DATA IS NEVER CACHED — see sw.js and the guard that enforces it.
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {
        // A worker that will not install is not worth an error message: the app
        // works without it, just without the instant open.
      });
    });
  }

  // Offline says offline. It does not show the last numbers it happened to have.
  function renderConnection() {
    const bar = document.getElementById('offline-bar');
    if (!bar) return;
    bar.hidden = navigator.onLine;
  }
  window.addEventListener('online', renderConnection);
  window.addEventListener('offline', renderConnection);

  async function boot() {
    renderConnection();
    skeleton(document.getElementById('week-cards'), 'skeleton-card', 3);
    try {
      await loadSports();
      state.meta = await fetchJSON(withSport('/api/meta'));
      renderBanner(state.meta);
      renderColophon(state.meta);
      state.scorecard = await fetchJSON(withSport('/api/scorecard'));
      await loadMarkets();
      await loadWeekPicker();
    } catch (err) {
      showError(err);
    }

    window.addEventListener('hashchange', route);
    ['chart-market', 'chart-predictor'].forEach(id =>
      document.getElementById(id).addEventListener('change', () => {
        try { renderRecord(); } catch (err) { showError(err); }
      }));
    ['week-picker', 'week-market'].forEach(id =>
      document.getElementById(id).addEventListener('change', () =>
        renderWeek().catch(showError)));
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

  return { boot, route, state, requireN, MissingSampleSize,
           drawCalibration, drawOverTime, dumbbell, contributions, bucketChip,
           fetchJSON };
})();

window.Gridiron = Gridiron;
document.addEventListener('DOMContentLoaded', () => { Gridiron.boot(); });
