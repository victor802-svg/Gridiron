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
  // An em-dash is a PROSE separator here — "Calibration — spread, 6 resolved" —
  // and nothing else. It is never a value.
  const DASH = '—';
  // What a data cell says when it has no value. A dash in a cell means nothing
  // to a reader and looks like a rendering fault; every absence names itself.
  const ABSENT = 'not recorded';
  const NO_LINE = 'no line';
  const NOT_PLAYED = 'not played';
  // The disagreement threshold the record uses, so the card and the edge
  // question mean the same thing by 'disagreed'.
  const DISAGREEMENT = 0.05;
  const pct = (x, dp) => (x === null || x === undefined) ? ABSENT : (x * 100).toFixed(dp === undefined ? 1 : dp) + '%';
  const num = (x, dp) => (x === null || x === undefined) ? ABSENT : Number(x).toFixed(dp === undefined ? 4 : dp);
  const int = (x) => (x === null || x === undefined) ? ABSENT : Number(x).toLocaleString();
  const signed = (x, dp) => (x === null || x === undefined) ? ABSENT : (x > 0 ? '+' : '') + Number(x).toFixed(dp === undefined ? 1 : dp);

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
  const state = {
    // Disagreement is the default order, and the note under the control
    // says why. Confidence-first would put the model's easiest calls on top.
    weekSort: 'disagreement', sport: 'nfl', sports: [], meta: null, scorecard: null,
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

    // `--ink` is the page GROUND in this palette; chart ink is `--chrome`.
    // Drawn in --ink these axes and labels were black on black.
    const ink = css('--chrome'), faint = css('--faint'), rule = css('--line');
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
      // Green ONLY where the bucket sits inside the acceptable band, red where
      // it does not. This is the positive/negative semantic doing its one job:
      // "this bucket is calibrated" is a value, not decoration.
      const inside = Math.abs(b.actual - b.claimed) <= ACCEPTABLE;
      ctx.fillStyle = inside ? css('--green') : css('--red');
      ctx.beginPath(); ctx.arc(x, y, b.provisional ? 3.5 : 5.5, 0, Math.PI * 2); ctx.fill();
      // A provisional point is drawn hollow: below the sample floor it is a
      // position, not a finding.
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
    // `--ink` is the page GROUND in this palette; chart ink is `--chrome`.
    // Drawn in --ink these axes and labels were black on black.
    const ink = css('--chrome'), faint = css('--faint'), rule = css('--line');
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
    // THE TIER TABLE LEADS. Rendered first and unconditionally: the charts
    // below it now live on the Factors page and may not be on screen at all.
    renderTierTable(sc.tier_table);
    loadTierMarkets((sc.tier_table || {}).prop_type ||
                    (sc.tier_table || {}).market_type);
    const market = document.getElementById('chart-market').value || 'spread';
    const predictor = document.getElementById('chart-predictor').value || 'statistical';
    const curve = findCurve(sc, market, predictor) || sc.headline;
    requireN(curve, 'calibration curve');

    const head = document.getElementById('record-headline');
    head.innerHTML = '';
    head.appendChild(el('div', '', curve.largest_gap));
    head.appendChild(el('div', 'sub',
      marketLabel(market) + ', ' + predictor + '. ' + int(curve.n) + ' resolved' +
      (curve.voided ? ', ' + int(curve.voided) + ' void' : '') +
      '. The sentence above always names the largest gap, never the best bucket.'));

    // These moved to the Factors page (R1), so they are not guaranteed to be
    // in the document when the Record tab renders. Guarded rather than
    // assumed: a missing element used to throw inside boot's catch, which is
    // how the market dropdowns sat empty for three sessions.
    const cap = document.getElementById('chart-caption');
    if (cap) {
      cap.textContent = DASH + ' ' + marketLabel(market) + ', ' + predictor +
        ' · ' + int(curve.n) + ' resolved';
    }
    const canvas = document.getElementById('calibration');
    if (canvas) drawCalibration(canvas, curve);
    const prose = document.getElementById('largest-gap-prose');
    if (prose) prose.textContent = curve.largest_gap;

    table(document.getElementById('bucket-table'),
      [{ label: 'Confidence bucket' }, { label: 'N' }, { label: 'Claimed' },
       { label: 'Actual' }, { label: 'Gap' }, { label: '' }],
      curve.buckets.map(b => {
        requireN(b, 'bucket row ' + b.label);
        return [
          b.label, int(b.n), pct(b.claimed), pct(b.actual),
          b.gap === null ? el('span', 'absent', 'nothing resolved yet')
                         : signed(b.gap * 100, 1) + ' pts',
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
      if (pair[1] === ABSENT) return;
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
    grid.appendChild(scoreCard(
      'Model on ' + marketLabel(market) + ', ' + predictor, curve.score));
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
        // An unscored category says WHY it has no numbers. Four em-dashes in a
        // row read as an error; "nothing resolved yet" reads as the truth.
        const empty = !c.score.n;
        const blank = () => el('span', 'absent', 'nothing resolved yet');
        return [
          categoryCell(c), int(c.score.n), int(c.voided),
          empty ? blank() : num(c.score.brier),
          empty ? el('span', 'absent', '') : num(c.score.log_loss),
          empty ? el('span', 'absent', '') : pct(c.score.hit_rate)
        ];
      }));
    wrap.appendChild(t);
    byCat.appendChild(wrap);
    host.appendChild(byCat);
  }

  // RULING R3: a gate that will not be reached and a gate that has not been
  // reached YET must not render the same way. "6 of 100" reads as progress; the
  // outlook line says which of the two it is, with the arithmetic beside it so
  // the reader does not have to take it on trust.
  function categoryCell(c) {
    const cell = el('div', 'cat-cell');
    // categoryLabel returns a STRING, not a node.
    cell.appendChild(el('div', '', categoryLabel(c.category)));
    const o = c.outlook;
    // ONLY WHERE THERE IS A RATE TO PROJECT FROM. The outlook counts THIS
    // season; the category's N counts the whole record. On a backtest, and on
    // any sport whose settled picks predate the current season, that put
    // "nothing written in this market yet" directly beside "N = 8" -- two true
    // statements that read as a contradiction. Silence beats a sentence the
    // reader has to reconcile.
    if (o && o.message && o.reachable !== null && o.reachable !== undefined) {
      const cls = o.reachable === false ? 'footnote gate-unreachable' : 'footnote';
      cell.appendChild(el('div', cls, o.message));
    }
    return cell;
  }

  // THE TIER TABLE. The Record tab's lead, in the same vocabulary the chips
  // on every pick use, answering the question a reader actually has: when it
  // says STRONG, is it?
  //
  // ONE ROW PER BAND, and STRONG appears twice. The brief called the buckets
  // and the tiers "the same partition"; they are not -- STRONG spans 70-80%
  // and 80%+, and pooling them would let the easier band lift the harder one,
  // which is the merge LAW 4 forbids.
  function renderTierTable(t) {
    if (!t) return;
    document.getElementById('tier-caption').textContent =
      DASH + ' ' + int(t.n) + ' settled, by how sure the model said it was';
    document.getElementById('tier-headline').textContent = t.headline;
    document.getElementById('tier-bands-note').textContent = t.bands_note;
    // One line on whether these numbers are raw or earned, in the same voice
    // as every other gate line on the page.
    const cn = document.getElementById('tier-corrections-note');
    if (cn) cn.textContent = t.corrections_note || '';

    table(document.getElementById('tier-table'),
      [{ label: 'Tier' }, { label: 'Band' }, { label: 'Settled' },
       { label: 'Right' }, { label: 'Claimed' }, { label: 'Actual' },
       { label: 'Verdict' }],
      t.rows.map(r => {
        // BELOW THE GATE, NO PERCENTAGES AT ALL. Not greyed, not italic, not
        // parenthesised: absent. A rate off nine settled picks is the most
        // persuasive lie the page could tell, sitting in a column of real
        // ones (LAW 4).
        const blank = () => el('span', 'absent', '');
        return [
          el('span', 'tier ' + String(r.tier || '').toLowerCase(), r.tier || ''),
          r.band,
          int(r.settled),
          r.proven ? int(r.right) : blank(),
          r.proven ? pct(r.claimed, 0) : blank(),
          r.proven ? pct(r.actual, 0) : blank(),
          el('span', r.proven ? 'verdict-words' : 'absent', r.verdict)
        ];
      }));
  }

  async function loadTierMarkets(current) {
    const sel = document.getElementById('tier-market');
    if (!sel || sel.dataset.sport === state.sport) return;
    sel.innerHTML = '';
    (state.markets || []).forEach(m => {
      const o = el('option', '', marketLabel(m));
      o.value = m;
      sel.appendChild(o);
    });
    sel.dataset.sport = state.sport;
    if (current) sel.value = current;
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

    const model = shownProb(card);
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
    marketBlock.appendChild(el('div', 'v' + (hasMarket ? '' : ' no-line'),
      hasMarket ? pct(market) : NO_LINE));
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
      // The plain phrase, with the code in the tooltip for anyone matching a
      // bar against the registry.
      const label = el('div', 'contrib-name', f.plain_name || f.factor);
      label.title = f.factor;
      row.appendChild(label);
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

  // THE NUMBER TO SHOW, and there is exactly one answer per card.
  //
  // `shown_prob` is the corrected claim where a category has an active
  // correction and the raw claim everywhere else; the server computes it once
  // at write time and stores both. Reading `model_prob` here instead put a
  // 74% headline on a card whose tier chip said SOLID, whose bucket line said
  // 60-70%, and whose own sentence underneath said "it is shown as 62%" --
  // four numbers describing one forecast, three of them agreeing and the
  // biggest one not. Caught by looking at the render, not by a test.
  const shownProb = (c) => (c.shown_prob === null || c.shown_prob === undefined)
    ? c.model_prob : c.shown_prob;

  // THE DESK (D2). One breakpoint, declared once, read by everything that
  // needs to know which layout is live. 1280 matches the mockup and the CSS;
  // a second literal somewhere else is how the two would drift apart.
  const DESK_MIN_WIDTH = 1280;
  const isDesk = () => window.innerWidth >= DESK_MIN_WIDTH;

  // A tile. Every string on it was written by the server: the matchup, the
  // short pick line, the label under the percentage. The renderer places
  // them and computes no words of its own (ruling, 2026-08-31).
  function pickTile(c, rank) {
    const tile = el('button', 'tile');
    tile.type = 'button';
    tile.dataset.id = c.prediction_id;
    tile.setAttribute('role', 'option');
    tile.setAttribute('aria-selected', 'false');
    // The tier as a class token, lowered where it is used so it reads as the
    // CSS token it is. (The prose scan exempts a class token by POSITION, and
    // it is right to: lowering a value into a variable first is how a word
    // being shaped for a reader would look.)
    if ((c.tier || {}).tier) tile.classList.add('t-' + c.tier.tier.toLowerCase());

    const top = el('div', 'tile-top');
    top.appendChild(el('div', 'tile-match', c.row_title || c.matchup || ''));
    // The rank is the position in the CURRENT sort, so it renumbers when the
    // toggle moves. A rank that survived a re-sort would be a different
    // ordering's opinion left lying on the page.
    top.appendChild(el('span', 'tile-rank', rank == null ? '' : String(rank)));
    tile.appendChild(top);

    const pick = el('div', 'tile-pick');
    pick.appendChild(el('b', '', c.tile_line || c.phrase || ''));
    // `start_local` is the UTC instant; the BROWSER applies the reader's
    // timezone, which is the one thing it knows better than the server.
    // `localTime` is the same helper the compact rows use -- without it
    // the tile printed '2026-09-05T16:00:00Z' at a reader.
    if (c.start_local) {
      pick.appendChild(document.createTextNode(' · ' + localTime(c.start_local)));
    }
    tile.appendChild(pick);

    const bottom = el('div', 'tile-bottom');
    const mkt = el('div', 'tile-mkt');
    if (c.market_implied_prob === null || c.market_implied_prob === undefined) {
      mkt.textContent = 'no line';
    } else {
      mkt.appendChild(document.createTextNode('market '));
      mkt.appendChild(el('b', '', pct(c.market_implied_prob, 0)));
      mkt.appendChild(el('br'));
      mkt.appendChild(document.createTextNode('gap '));
      mkt.appendChild(el('b', '', (c.gap * 100 >= 0 ? '+' : '') + (c.gap * 100).toFixed(0)));
    }
    bottom.appendChild(mkt);

    const p = el('div', 'tile-pct');
    p.appendChild(document.createTextNode(pct(shownProb(c), 0).replace('%', '')));
    p.appendChild(el('i', '', '%'));
    p.appendChild(el('small', '', c.tile_label || ''));
    bottom.appendChild(p);
    tile.appendChild(bottom);

    tile.addEventListener('click', () => selectTile(tile));
    return tile;
  }

  //: Which tile the rail is describing. D3 fills the rail; D2 only has to
  //: make the selection exist, be visible, and never move the frame.
  let selectedTile = null;

  function selectTile(tile) {
    if (!tile) return;
    // THE FRAME MUST NOT MOVE. Selecting a pick is not navigation, and a
    // reader half way down a 177-pick slate who loses their place has been
    // punished for looking at something. Asserted in the browser tests.
    const frame = document.getElementById('week-frame');
    const keep = frame ? frame.scrollTop : 0;
    document.querySelectorAll('.tile[aria-selected="true"]')
      .forEach(t => t.setAttribute('aria-selected', 'false'));
    tile.setAttribute('aria-selected', 'true');
    selectedTile = tile;
    if (typeof paintRail === 'function') paintRail(tile);
    if (frame) frame.scrollTop = keep;
  }

  // Arrow keys walk the grid, Enter and Space select. Three across, so up and
  // down move by three -- the same distance the eye moves.
  function deskKeys(event) {
    if (!isDesk()) return;
    const tiles = [...document.querySelectorAll('#week-frame .tile')];
    if (!tiles.length) return;
    const here = tiles.indexOf(document.activeElement);
    const step = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: 3, ArrowUp: -3 }[event.key];
    if (step === undefined) {
      if ((event.key === 'Enter' || event.key === ' ') && here >= 0) {
        event.preventDefault();
        selectTile(tiles[here]);
      }
      return;
    }
    event.preventDefault();
    const next = tiles[Math.min(tiles.length - 1, Math.max(0, (here < 0 ? 0 : here) + step))];
    if (next) next.focus();
  }

  // THE RAIL'S PANELS (D3). Every string placed here was composed on the
  // server; this positions them and computes no words of its own.

  //: The cards of the slate currently rendered, by prediction id, so the rail
  //: describes THE SAME OBJECT the tile was built from. Looking the pick up
  //: again from the DOM would be a second source for one fact.
  let slateCards = new Map();

  function paintRail(tile) {
    const card = slateCards.get(tile && tile.dataset.id);
    const match = document.getElementById('rail-match');
    if (!card || !match) return;

    match.textContent = card.row_title || card.matchup || '';

    // The subline is three server-written parts with a separator between
    // them, and a part that is absent is simply not there -- no dash, no
    // placeholder. The time is the one thing the browser is better placed to
    // know, so it renders the instant the server sent.
    const sub = document.getElementById('rail-sub');
    const parts = [];
    if (card.start_local) parts.push(localTime(card.start_local));
    if (card.venue) parts.push(card.venue);
    if (card.market_label) parts.push(card.market_label);
    sub.textContent = parts.join(' \u00b7 ');

    const pick = document.getElementById('rail-pick');
    pick.innerHTML = '';
    pick.appendChild(el('b', '', card.phrase || card.tile_line || ''));

    // THE SAME BODY THE EXPANDED ROW SHOWS, from the same function: the
    // probability rail, the gap and bucket line, the earned number where a
    // correction moved it, the three-sentence why, the link and the tier
    // line. A second implementation here would be a second chance to
    // disagree with the record about what the model said.
    buildRowBody(document.getElementById('rail-body'), card);
  }

  function paintGlance(glance) {
    const count = document.getElementById('rail-glance-count');
    const windows = document.getElementById('rail-windows');
    const facts = document.getElementById('rail-facts');
    if (!windows || !facts) return;
    if (!glance) { windows.innerHTML = ''; facts.innerHTML = ''; return; }

    count.textContent = glance.games + (glance.games === 1 ? ' game' : ' games');

    windows.innerHTML = '';
    glance.windows.forEach(w => {
      const row = el('div', 'krow');
      row.appendChild(el('span', '', w.name));
      const bar = el('span', 'bar2');
      const fill = el('i');
      fill.style.width = Math.round(w.share * 100) + '%';
      bar.appendChild(fill);
      row.appendChild(bar);
      row.appendChild(el('b', '', String(w.n)));
      windows.appendChild(row);
    });
    windows.appendChild(el('div', 'rail-note', glance.windows_note));

    facts.innerHTML = '';
    // COVERAGE IS REPORTED, NEVER USED TO CHOOSE (ruling R-A). Each row is
    // one market's priced-of-asked, and the note underneath says why the two
    // numbers can differ at all.
    glance.coverage.forEach(c => {
      const row = el('div', 'krow');
      row.appendChild(el('span', '', c.market));
      row.appendChild(el('b', '', c.priced + ' of ' + c.asked));
      facts.appendChild(row);
    });
    const sharp = el('div', 'krow');
    sharp.appendChild(el('span', '', glance.labels.sharpest));
    sharp.appendChild(el('b', '', glance.sharpest.line));
    facts.appendChild(sharp);
    const tiers = el('div', 'krow');
    tiers.appendChild(el('span', '', glance.labels.tiers));
    tiers.appendChild(el('b', '', glance.tiers.line));
    facts.appendChild(tiers);
    facts.appendChild(el('div', 'rail-note', glance.coverage_note));
  }

  // THE GREETING IS MOVED, NOT REDRAWN. On the desk the wrapper is appended
  // into the rail's panel; below the breakpoint it goes back where the markup
  // put it. Same nodes, same ids, same click handler -- so there is one
  // greeting in the document and it cannot disagree with itself.
  function placeGreeting() {
    const greeting = document.getElementById('greeting');
    const panel = document.getElementById('rail-since-host');
    const home = document.getElementById('greeting-home');
    if (!greeting || !panel || !home) return;
    const wanted = (isDesk() && state.view === 'week') ? panel : home;
    if (greeting.parentElement !== wanted) wanted.appendChild(greeting);
  }

  // --- the pick card ------------------------------------------------------
  // Rebuilt to docs/mockup/gridiron_dark.html. The order is the order the
  // questions arrive in: who is playing, what the model thinks, how sure, where
  // the market sits, how that tier has really done, and only then why.

  // `pickSentence` WAS DELETED HERE, and finding out why took longer than the
  // deletion. Ruling 1 says the frontend composes no prose, and this function
  // was the clearest violation left in the file: a static lead, an uppercased
  // data field, and -- when the server sent no phrase -- an else branch that
  // took the raw subject and appended a verb chosen by market type. That verb
  // table is the K1 defect, which put "97% chance WAS covers" on 34 cards.
  //
  // It had ZERO CALLERS. K2 replaced the pick card with `pickRow`, and this
  // went with the old card except that nobody removed it, so the K1 shape sat
  // in the file looking like live code for two sessions. Rewriting it to
  // comply would have shipped a server function nobody called to feed a
  // renderer nobody called; the orphan scan would then have failed the build,
  // correctly, on the mess I had just made.
  //
  // This is exactly the sweep ruling 2 defers -- dead-but-named code in
  // app.js, which no scan looks at today. Recorded in FOLLOWUPS.

  function tierChip(c) {
    const t = c.tier || {};
    if (!t.tier) return null;
    const holder = el('div');
    holder.appendChild(el('span', 'tier ' + t.tier.toLowerCase(), t.tier));
    // The earned figure, or the shortfall. Never a hit rate below the gate:
    // a tier showing an accuracy on nine settled picks reads as a track record
    // for the pick beside it, which is the most persuasive lie available here.
    holder.appendChild(el('span', 'tier-score', t.message));
    return holder;
  }

  function probBlock(c) {
    const box = el('div', 'prob');
    box.appendChild(document.createTextNode(pct(shownProb(c), 0).replace('%', '')));
    box.appendChild(el('span', 'pct', '%'));
    // THE VERB TABLE THAT USED TO LIVE HERE IS GONE, and its absence is the
    // fix. It hardcoded a verb per market type, so every prop read "goes over"
    // whichever side the model took; M4 fixed that branch and left the spread
    // branch reading "covers" on all 34 cards where the model had said the
    // opposite. Fixing the second branch here would have left the third.
    //
    // The server sends the side in words now, from the same humaniser that
    // writes the pick sentence, so the two cannot disagree.
    box.appendChild(el('small', '', 'chance ' + (c.chance_clause || '')));
    return box;
  }

  // THE RAIL. 0-100 with a tick at 50; the model solid, the market hollow, the
  // disagreement shaded between them. Where no market line exists there is one
  // dot and a sentence — never a second dot at a number nobody published.
  function rail(c) {
    const wrap = el('div', 'dumbbell');
    const r = el('div', 'rail');
    r.appendChild(el('div', 'track'));
    r.appendChild(el('div', 'tick50'));

    const model = clamp01(shownProb(c)) * 100;
    const market = (c.market_implied_prob === null || c.market_implied_prob === undefined)
      ? null : clamp01(c.market_implied_prob) * 100;

    if (market !== null) {
      const span = el('div', 'span');
      span.style.left = Math.min(model, market) + '%';
      span.style.width = Math.abs(model - market) + '%';
      r.appendChild(span);

      const md = el('div', 'dot market');
      md.style.left = market + '%';
      r.appendChild(md);
      // PLAIN WORDS. This label read 'MKT' until the desk put it at
      // 24px in the rail panel and it became obvious that an
      // abbreviation nobody defined was sitting on the page. The tile
      // beside it has always said 'market'.
      const ml = el('div', 'dot-label', 'market ' + Math.round(market));
      ml.style.left = market + '%';
      r.appendChild(ml);
    }

    const dot = el('div', 'dot model');
    dot.style.left = model + '%';
    r.appendChild(dot);
    const label = el('div', 'dot-label', String(Math.round(model)));
    label.style.left = model + '%';
    r.appendChild(label);

    r.appendChild(el('span', 'zero', '0'));
    r.appendChild(el('span', 'hundred', '100'));
    wrap.appendChild(r);

    if (market === null) {
      wrap.appendChild(el('div', 'rail-noline',
        'no line available' +
        (c.line_availability && c.line_availability.reason
          ? ' — ' + c.line_availability.reason : '')));
    }
    return wrap;
  }

  function clamp01(v) {
    return Math.max(0, Math.min(1, typeof v === 'number' ? v : 0.5));
  }

  function bucketLine(c) {
    const b = c.bucket || {};
    const bits = [b.label + ' bucket', requireN(b, 'bucket line') + ' resolved'];
    if (b.provisional) bits.push('too few to grade');
    return el('span', 'bucket', bits.join(' · '));
  }

  function factorChips(c) {
    const rows = (c.top_factors || [])
      .filter(f => f.contribution !== null && f.contribution !== undefined)
      .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
      .slice(0, 4);
    if (!rows.length) return null;
    const host = el('div', 'factors');
    rows.forEach(f => {
      const chip = el('span', 'chip');
      chip.appendChild(document.createTextNode(readableFactor(f.factor) + ' '));
      chip.appendChild(el('b', '', signed(f.contribution, 1)));
      host.appendChild(chip);
    });
    return host;
  }

  function readableFactor(name) {
    return String(name).replace(/^(nfl|mlb|nba)_/, '').replace(/_/g, ' ');
  }

  function localTime(iso) {
    try {
      return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    } catch (err) { return iso; }
  }

  // --- THIS WEEK ----------------------------------------------------------
  // ============================================================
  // THE COMPACT ROW
  // ============================================================
  //
  // Five things visible: rank, matchup, what it picks, the chance, the tier.
  // Everything else is behind a tap. The full card put a rail, a gap figure, a
  // bucket line, a decomposition and three rationale essays on screen for every
  // forecast, so a slate of eight filled several screens and the reader scrolled
  // past the picks to find the picks.
  //
  // Nothing here builds a sentence. `row_title`, `phrase`, `chance_clause` and
  // `bucket_line` all arrive written from `language.py`, which is what stopped
  // the renderer inventing a verb and getting the side backwards twice.

  function pickRow(c, rank) {
    const row = el('div', 'row');
    row.dataset.id = c.prediction_id;

    const head = el('div', 'row-head');
    head.setAttribute('role', 'button');
    head.setAttribute('tabindex', '0');
    head.setAttribute('aria-expanded', 'false');

    head.appendChild(el('div', 'row-rank', rank == null ? '' : String(rank)));

    const mid = el('div', 'row-mid');
    const title = el('div', 'row-title', c.row_title || c.matchup || '');
    // The phone folds the rank into this line via a CSS ::before, so the
    // ordinal is carried on the element that survives the layout change.
    if (rank != null) title.dataset.rank = rank;
    mid.appendChild(title);
    const pick = el('div', 'row-pick');
    pick.appendChild(el('span', 'row-caret', '\u25B8'));
    pick.appendChild(el('span', 'row-phrase', c.phrase || ''));
    const tail = rowTail(c);
    if (tail) pick.appendChild(el('span', 'row-when', ' \u00B7 ' + tail));
    mid.appendChild(pick);
    head.appendChild(mid);

    const prob = el('div', 'prob');
    prob.appendChild(document.createTextNode(pct(shownProb(c), 0).replace('%', '')));
    prob.appendChild(el('span', 'pct', '%'));
    prob.appendChild(el('small', '', c.chance_clause || ''));
    head.appendChild(prob);

    head.appendChild(tierChip(c.tier));
    row.appendChild(head);

    // Built once, on first open. A slate of 25 would otherwise render 25
    // rails, 25 decompositions and 25 why-texts nobody has asked to see.
    const body = el('div', 'row-body');
    body.hidden = true;
    row.appendChild(body);

    let built = false;
    const toggle = () => {
      if (!built) { buildRowBody(body, c); built = true; }
      body.hidden = !body.hidden;
      head.setAttribute('aria-expanded', String(!body.hidden));
      row.classList.toggle('open', !body.hidden);
    };
    head.addEventListener('click', toggle);
    head.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
        e.preventDefault();
        toggle();
      }
    });
    return row;
  }

  // What follows the pick on the line: kick-off for a game, the fixture for a
  // prop, because on a prop the subject is the headline and the fixture is the
  // detail.
  function rowTail(c) {
    if (c.market_type === 'prop') return c.matchup || '';
    return c.start_local ? localTime(c.start_local) : '';
  }

  function localTime(iso) {
    try {
      return new Date(iso).toLocaleTimeString([], {
        hour: 'numeric', minute: '2-digit'
      });
    } catch (e) { return ''; }
  }

  function tierChip(tier) {
    // `.tier` with a modifier, which is what the stylesheet and the approved
    // mockup both define. K2 emitted `chip chip-lean`, for which no rule
    // exists -- the chips have been rendering with base styling only and
    // nothing said so, because an unstyled element is still an element.
    if (!tier || !tier.tier) return el('span', 'tier tier-none', '');
    const chip = el('span', 'tier ' + tier.tier.toLowerCase(), tier.tier);
    chip.title = tier.message || '';
    return chip;
  }

  function buildRowBody(body, c) {
    body.innerHTML = '';
    body.appendChild(rail(c));

    const line = el('div', 'row-stats');
    line.appendChild(el('span', 'row-gap',
      c.gap === null || c.gap === undefined
        ? 'no line' : 'gap ' + (c.gap * 100 >= 0 ? '+' : '') + (c.gap * 100).toFixed(1)));
    line.appendChild(el('span', 'row-bucket', c.bucket_line || ''));
    body.appendChild(line);

    // THE RAW CLAIM, ONE TAP AWAY. Present only where a correction actually
    // moved the number, so a card in a raw category is byte-identical to what
    // it was before corrections existed. The sentence is written by the
    // server; this places it.
    if (c.earned_line) {
      body.appendChild(el('p', 'earned-line', c.earned_line));
    }

    // THE PLAIN WHY (K3). The contribution bars and the decomposition sentence
    // that used to sit here have moved to the Factors page, which is where
    // somebody auditing the model goes looking for them. What a reader wants on
    // a pick is which few things drove it and how hard, in words.
    //
    // Every sentence is written by `language.why_block` from the SAME
    // contributions the decomposition uses, so the prose and the arithmetic
    // cannot disagree about direction or order.
    const why = el('div', 'row-why');
    const w = c.why;
    if (w && (w.sentences || []).length) {
      why.appendChild(el('b', '', w.heading + ':'));
      w.sentences.forEach(sentence => {
        why.appendChild(document.createTextNode(' ' + sentence));
      });
      // THE MARKET IS SENTENCE THREE now, inside `sentences`. Appending it
      // here as well printed it twice -- the server took over a job the
      // renderer was still doing, which is the two-implementations smell in
      // its smallest form.
      if (w.absent) {
        why.appendChild(el('span', 'why-absent', ' ' + w.absent));
      }
    } else if (c.reasoning) {
      // A pick whose factors carry no declared phrase still says something
      // rather than showing an empty box.
      why.textContent = c.reasoning;
    }
    body.appendChild(why);

    const more = el('a', 'row-more',
      ((w && w.more_label) || 'How the model works') + ' \u2192');
    more.href = (w && w.more_href) || '#/factors';
    body.appendChild(more);

    if (c.tier && c.tier.message) {
      body.appendChild(el('div', 'row-tierline',
        (c.tier.tier || '') + ' tier ' + c.tier.message.replace(/^tier /, '')));
    }
  }

  function resolvedRow(c) {
    const row = el('div', 'row row-done');
    const head = el('div', 'row-head');
    head.appendChild(el('div', 'row-rank', ''));
    const mid = el('div', 'row-mid');
    mid.appendChild(el('div', 'row-title', c.matchup || ''));
    mid.appendChild(el('div', 'row-pick', c.resolved_story || c.phrase || ''));
    head.appendChild(mid);
    const prob = el('div', 'prob');
    prob.appendChild(document.createTextNode(pct(shownProb(c), 0).replace('%', '')));
    prob.appendChild(el('small', '', 'model'));
    head.appendChild(prob);
    // `.verdict`, matching the approved mockup's class rather than reusing the
    // tier chip: a verdict and a confidence tier are different things and
    // sharing a class invites them to be styled alike.
    const word = c.voided ? 'VOID' : (c.outcome === 1 ? 'WIN' : 'LOSS');
    head.appendChild(el('span', 'verdict ' + word.toLowerCase(), word));
    row.appendChild(head);
    return row;
  }

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
    // The standing note, in the mockup's words. Agreeing with the market is
    // not a finding, which is why disagreement is the default order.
    document.getElementById('week-sort').textContent =
      state.weekSort === 'confidence'
        ? 'Sorted by how sure the model is. ' + data.n + ' forecasts.'
        : 'Agreeing confidently with the market is not a finding.';

    host.innerHTML = '';
    let cards = market ? data.cards.filter(c => c.market === market) : data.cards;
    // Indexed BEFORE the market filter narrows the view, so the rail can still
    // describe a pick the reader selected under a different filter.
    slateCards = new Map(data.cards.map(c => [String(c.prediction_id), c]));
    if (state.weekSort === 'confidence') {
      cards = cards.slice().sort((a, b) => (shownProb(b) || 0) - (shownProb(a) || 0));
    }

    // THE RAIL. Hidden below the breakpoint, and hidden on a slate with no
    // open picks -- an empty detail panel beside an empty frame is two ways of
    // saying the same nothing.
    const rail = document.getElementById('week-rail');
    if (rail) rail.hidden = true;
    paintGlance(isDesk() ? data.glance : null);
    placeGreeting();

    // A resolved forecast is not a pick. Split rather than filtered, so the
    // slate can show both without a reader mistaking last night for tonight.
    const open = cards.filter(c => c.resolved_utc === null && !c.voided);
    const done = cards.filter(c => c.resolved_utc !== null || c.voided);

    // THE CONTROLS LINE. A thin slate has to explain itself: eight picks on a
    // fourteen-game card looks like a failure until the floor is named.
    const counts = document.getElementById('week-counts');
    if (counts) {
      const bits = [data.slate_word === 'day' ? 'tonight' : 'this week',
                    open.length + (open.length === 1 ? ' pick' : ' picks')];
      if (data.below_floor) {
        bits.push(data.below_floor + ' below the ' +
                  Math.round((data.floor || 0.7) * 100) + '% floor');
      }
      counts.textContent = bits.join(' \u00B7 ');
    }

    if (!open.length && !done.length) {
      host.appendChild(el('div', 'empty', data.message ||
        (market ? 'No ' + marketLabel(market) + ' forecasts on this slate.'
                : 'No forecasts recorded for this slate yet.')));
      (data.quiet_markets || []).forEach(q =>
        host.appendChild(el('div', 'quiet-market', q)));
      return;
    }

    if (open.length) {
      // ONE GRID, NO SECTIONS, on the desk. The mockup has no confidence
      // headings: the sort toggle already says how the slate is ordered, and a
      // section label would be a second, quieter claim about the same thing.
      // Below the breakpoint the compact rows render exactly as they did.
      if (isDesk()) {
        const grid = el('div', 'tiles');
        rail.hidden = false;
        grid.setAttribute('role', 'listbox');
        grid.setAttribute('aria-label', 'Picks on this slate');
        open.forEach((c, i) => grid.appendChild(pickTile(c, i + 1)));
        host.appendChild(grid);
        // The rail is always populated, so the first tile is selected on
        // arrival rather than leaving an empty panel asking to be clicked.
        selectTile(grid.querySelector('.tile'));
      } else {
        const list = el('div', 'rows');
        open.forEach((c, i) => list.appendChild(pickRow(c, i + 1)));
        host.appendChild(list);
      }
    }
    // A market the slate asked nothing in says so, rather than leaving a gap
    // that reads as a failure to find questions.
    (data.quiet_markets || []).forEach(q =>
      host.appendChild(el('div', 'quiet-market', q)));

    if (done.length) {
      host.appendChild(el('div', 'section-label', 'Resolved'));
      const list = el('div', 'rows rows-done');
      done.forEach(c => list.appendChild(resolvedRow(c)));
      host.appendChild(list);
    }
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
    // `game_markets`, not `spread`. s1 renamed this field on the server and
    // the browser was never updated, so `data.spread.concat` threw on every
    // boot — silently, because it happened inside boot's catch. The week
    // picker and the chart's market selector have been EMPTY ever since,
    // and no test looked at them.
    state.markets = (data.game_markets || []).concat(data.props || []);
    // Labels come from the server so every page says the same words.
    state.marketLabels = data.labels || {};
    const chart = document.getElementById('chart-market');
    chart.innerHTML = '';
    state.markets.forEach(m => {
      const o = el('option', '', marketLabel(m)); o.value = m; chart.appendChild(o);
    });
    // CLEARED BEFORE REFILLING, like the chart select above. These two only
    // appended, so every sport switch stacked the new sport's markets on top of
    // the previous one's: on MLB the filter offered `spread`, `passing_yards`
    // and `receptions`, none of which baseball has, and a reader could pick a
    // market that could not appear. The "all markets" option is markup rather
    // than data, so it is put back rather than kept.
    ['week-market', 'history-market'].forEach(id => {
      const sel = document.getElementById(id);
      const keep = sel.value;
      sel.innerHTML = '';
      const all = el('option', '', 'all markets'); all.value = '';
      sel.appendChild(all);
      state.markets.forEach(m => {
        const o = el('option', '', marketLabel(m)); o.value = m; sel.appendChild(o);
      });
      // A filter that survives the switch only if the new sport has it.
      sel.value = state.markets.includes(keep) ? keep : '';
    });
  }

  // --- VERSIONS -----------------------------------------------------------
  async function renderVersions() {
    const data = await fetchJSON(withSport('/api/versions'));
    requireN(data, 'version comparison');
    // The last place the raw code reached a reader: "current: fs2". The set
    // in force is named by when it began, like every other mention of one.
    const cur = (data.versions || []).find(v => v.status === 'current');
    const curStarted = cur && cur.activated_utc ? cur.activated_utc.slice(0, 10) : null;
    document.getElementById('versions-caption').textContent =
      DASH + (curStarted ? ' in force since ' + curStarted : ' current set');
    document.getElementById('versions-note').textContent = data.note;

    const host = document.getElementById('versions-list');
    host.innerHTML = '';
    const grid = el('div', 'scores');
    data.versions.forEach(v => {
      const card = el('div', 'score-card');
      // NOT the version code. This page is ABOUT factor sets, which makes it
      // the last place a reader should have to decode one: "fs2" says neither
      // what changed nor when. The heading is the date the set began, which is
      // the thing that distinguishes one from another to a person, and the
      // code stays in the tooltip for matching against a stored row.
      const started = (v.activated_utc || '').slice(0, 10);
      const h = el('h3', '', (started ? 'Set of ' + started : 'Undated set') + ' ');
      // A CLOSED SET IS NOT A WARNING. It carried `tag warn`, which reads as
      // red now that the warn colours are actually warning colours -- and a
      // superseded factor set is the most ordinary thing on this page: every
      // set becomes closed the moment the next one starts.
      h.appendChild(el('span', 'tag', v.status));
      h.appendChild(nTag(v.n));
      card.appendChild(h);
      card.appendChild(el('div', 'card-meta',
        int(v.predictions_written) + ' written · ' +
        int(v.open) + ' open'));
      // WHAT changed, not only when. Composed server-side from the registry's
      // own dates, so this line cannot disagree with the Factors page.
      if (v.changed) card.appendChild(el('p', 'set-changed', v.changed));
      // THE FULL LIST, under the summary. The line above names two and counts
      // the rest; the count must not be where the rest goes to die.
      if (v.changed_detail) card.appendChild(changeList(v.changed_detail));
      if (v.message) {
        card.appendChild(el('div', 'empty', v.message));
      } else {
        const wrap = el('div', 'table-scroll');
        const t = el('table', 'grid');
        table(t, [{ label: 'Category' }, { label: 'N' }, { label: 'Brier' },
                  { label: 'Hit rate' }],
          v.categories.filter(c => c.n > 0).map(c => {
            requireN(c, 'version ' + v.version + ' / ' + c.category);
            // Categories arrive as `market / forecaster`; the market half is
            // an internal name and must be said in words.
            return [categoryLabel(c.category), int(c.n), num(c.brier),
                    pct(c.hit_rate)];
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

  // Every change in a set, in full, under the sentence that summarises two of
  // them. Each group is labelled by what happened rather than by a field name,
  // and each entry is the factor's plain phrase with its code in the tooltip --
  // the same pairing the Factors table uses.
  const CHANGE_GROUPS = [
    ['joined', 'Added'],
    ['tried_and_dropped', 'Declared and withdrawn the same day'],
    ['left', 'Retired']
  ];

  function changeList(detail) {
    const host = el('div', 'set-detail');
    CHANGE_GROUPS.forEach(pair => {
      const items = detail[pair[0]] || [];
      if (!items.length) return;
      host.appendChild(el('div', 'set-detail-head', pair[1] + ' (' + items.length + ')'));
      const list = el('ul', 'set-detail-list');
      items.forEach(item => {
        const li = el('li', '', item.phrase || item.name || '');
        li.title = item.name || '';
        list.appendChild(li);
      });
      host.appendChild(list);
    });
    return host;
  }

  // --- FACTORS ------------------------------------------------------------
  // The decomposition, moved off the pick cards (K3). One real forecast from
  // the current slate, with its bars and the sentence that used to sit under
  // every card. Failing to load it hides the section rather than showing an
  // empty frame: this is supporting material, and a broken example is worse
  // than none.
  async function renderWorkedExample() {
    const host = document.getElementById('factors-worked');
    if (!host) return;
    try {
      const data = await fetchJSON(withSport('/api/week'));
      const card = (data.cards || []).find(c => (c.top_factors || []).length);
      if (!card) { host.hidden = true; return; }

      document.getElementById('worked-caption').textContent =
        DASH + ' ' + (card.phrase || '') + ', ' + pct(shownProb(card), 0);
      const bars = document.getElementById('worked-bars');
      bars.innerHTML = '';
      bars.appendChild(contributions(card));
      // NOT `card.reasoning`. That is the STATISTICAL DECOMPOSITION, written
      // when the prediction was made and stored with it -- "asked_line = -0.5
      // pushed..." -- so it names factor codes in a sentence, on the one page
      // whose job is explaining. It cannot be rewritten (LAW 3: a prediction is
      // never edited after the fact), and it does not need to be: K3's plain
      // why is built from the same contributions and says the same thing in
      // words. The raw form stays in the tooltip for anyone who wants it.
      const worked = document.getElementById('worked-sentence');
      worked.textContent = ((card.why && card.why.sentences) || []).join(' ')
        || '';
      worked.title = card.reasoning || '';
      host.hidden = false;
    } catch (err) {
      host.hidden = true;
      console.error('worked example failed:', err);
    }
  }

  async function renderFactors() {
    const data = await fetchJSON(withSport('/api/factors'));
    requireN(data, 'factor report');
    document.getElementById('factors-caption').textContent =
      DASH + ' scored over ' + int(data.n) + ' resolved statistical predictions';
    document.getElementById('factors-method').textContent = data.method;
    await renderWorkedExample();

    table(document.getElementById('factors-table'),
      [{ label: 'Factor' }, { label: 'Added' }, { label: 'Applies to' },
       { label: 'N' }, { label: 'Rows measured' }, { label: 'Δ Brier' },
       { label: 'Effect' }, { label: 'Verdict' },
       { label: 'Why it was declared', cls: 'wide' }],
      data.factors.map(f => {
        requireN(f, 'factor row ' + f.factor);
        // THE PLAIN NAME LEADS, the code goes underneath small. This page is
        // allowed to be dense; it is still read by a person, and the phrase a
        // pick card uses for a factor is what that factor is called.
        const name = el('div', 'factor-name');
        name.appendChild(el('div', '', f.plain_name || f.factor));
        name.appendChild(el('div', 'factor-code', f.factor));
        // Nor is a retired factor. LAW 2 makes retirement a dated, deliberate
        // act with a written reason -- "a repair is not a discovery" -- and
        // three of them were retired the day they were declared, on the
        // measurement. That is the process working, not an alarm.
        if (!f.active) name.appendChild(el('span', 'tag', 'inactive'));
        return [
          name, (f.added_utc || '').slice(0, 10), f.applies_to.join(', '),
          int(f.n), int(f.training_rows_measured),
          (f.delta_brier === null || f.delta_brier === undefined)
            ? el('span', 'absent', 'nothing resolved yet') : signed(f.delta_brier, 5),
          // The effect in WORDS with its sample beside it, and the raw figure
          // kept in the title for anyone auditing.
          (() => {
            const cell = el('span', '', f.earned_words || '');
            cell.title = 'mean |effect| ' + num(f.mean_abs_contribution, 4).textContent;
            return cell;
          })(),
          f.verdict,
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

  // PENDING / WIN / LOSS / VOID, in the card language. "open" is not a word
  // anybody says about a forecast that has not happened yet.
  // "receiving_yards / statistical" -> "receiving yards, statistical"
  function categoryLabel(category) {
    const parts = String(category).split(' / ');
    const market = marketLabel(parts[0]);
    return parts.length > 1 ? market + ', ' + parts[1] : market;
  }

  function marketLabel(name) {
    return (state.marketLabels && state.marketLabels[name])
      || String(name).replace(/_/g, ' ');
  }

  function resultChip(item) {
    const word = item.result || 'PENDING';
    const chip = el('span', 'result-chip ' + word.toLowerCase(), word);
    if (word === 'VOID' && item.void_reason) chip.title = item.void_reason;
    return chip;
  }

  async function renderHistory() {
    const data = await fetchJSON(withSport('/api/history?' + historyQuery()));
    requireN(data, 'history');
    state.historyTotal = data.n;
    document.getElementById('history-caption').textContent =
      int(data.n) + ' predictions match';

    // The forecaster column appears ONLY when both are being shown. A column
    // that always says "statistical" is a column of noise.
    const predictorFilter = document.getElementById('history-predictor').value;
    const showForecaster = !predictorFilter;

    const columns = [{ label: 'Prediction', cls: 'wide' }, { label: 'Date' },
                     { label: 'Week' }, { label: 'Model' },
                     { label: 'Market then' }, { label: 'Tier' },
                     { label: 'Result' }];
    if (showForecaster) columns.splice(3, 0, { label: 'Forecaster' });

    table(document.getElementById('history-table'), columns,
      data.items.map(i => {
        const row = [
          // One sentence, built on the server so the card, this table and the
          // digest cannot drift into three vocabularies.
          i.phrase,
          (i.created_utc || '').slice(0, 10),
          'wk ' + i.week,
          pct(shownProb(i), 1),
          // "no line" in WORDS. A bare dash reads as an error rather than an
          // absence, and absence here is a fact about the market, not a fault.
          (i.market_implied_prob === null || i.market_implied_prob === undefined)
            ? el('span', 'absent', 'no line')
            : pct(i.market_implied_prob, 1),
          // The tier it was CLAIMED at, beside how it turned out. The Record
          // tab grades the tiers now, so a settled row should say which one it
          // belongs to without being opened.
          tierChip(i.tier),
          resultChip(i)
        ];
        if (showForecaster) row.splice(3, 0, i.predictor);
        return row;
      }));

    const from = data.n ? state.historyOffset + 1 : 0;
    document.getElementById('history-range').textContent =
      from + '–' + (state.historyOffset + data.returned) + ' of ' + int(data.n);
    document.getElementById('history-prev').disabled = state.historyOffset === 0;
    document.getElementById('history-next').disabled =
      state.historyOffset + data.returned >= data.n;
  }

  // --- sport tabs ---------------------------------------------------------
  // The active sport's own settled record. Never a total: LAW 6 means the
  // header shows whichever sport is being looked at, and the never-summed note
  // moves to a quiet footer line.
  function wireSortToggle() {
    const seg = document.getElementById('week-sort-seg');
    if (!seg) return;
    seg.querySelectorAll('button').forEach(button => {
      button.addEventListener('click', () => {
        state.weekSort = button.dataset.sort;
        seg.querySelectorAll('button').forEach(b => {
          b.setAttribute('aria-pressed', b === button ? 'true' : 'false');
        });
        renderWeek().catch(showError);
      });
    });
  }

  async function renderRecordLine() {
    const host = document.getElementById('record-line');
    if (!host) return;
    try {
      const data = await fetchJSON(withSport('/api/record-line'));
      // The record is what this strip is for. The freshness time moves to the
      // tooltip because the two together never fit the slot -- see the note in
      // views.record_line -- and the Schedule page carries "last ran" in full
      // for anyone who needs the real answer.
      host.textContent = data.line;
      host.title = (data.label || '') + ' ' + (data.season || '') +
        ' season to date' + (data.updated_utc
          ? ', last updated ' + new Date(data.updated_utc).toLocaleString()
          : '; nothing settled yet');
    } catch (err) {
      host.textContent = '';
    }
  }

  async function loadSports() {
    const data = await fetchJSON('/api/sports');
    state.sports = data.sports;
    const host = document.getElementById('sport-tabs');
    host.innerHTML = '';
    data.sports.forEach(sp => {
      const b = el('button', '', sp.label);
      // LAW 4 in the navigation: the count rides on the tab, so an empty
      // record is visible before the tab is clicked rather than after. The bar
      // is 52px now, so it is the NUMBER with the word in the title -- the law
      // wants the count present, not a particular notation, and the tooltip
      // keeps the noun for anyone who wants it.
      const n = el('span', 'tab-n', String(int(sp.n)));
      b.appendChild(n);
      b.title = sp.label + ': ' + int(sp.n) + ' settled';
      b.setAttribute('aria-pressed', sp.sport === state.sport ? 'true' : 'false');
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
      const on = b.dataset.sport === sport;
      b.setAttribute('aria-current', on ? 'true' : 'false');
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    try {
      await renderRecordLine();
      await renderGreeting();
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
    // Said by the server. It was `meta.database_kind.toUpperCase() + ' DATABASE
    // — '`: a label built in the browser out of a stored value, which is the
    // pattern this file is no longer allowed to contain.
    banner.appendChild(el('strong', '', meta.database_label || ''));
    banner.appendChild(document.createTextNode(meta.database_note || ''));
  }

  // The footer is one server-written sentence now. It used to be five,
  // assembled here: a sliced timestamp glued to "Current factor set since ", a
  // count glued to " predictions on record", a spend through `toFixed`. Each
  // of those is a decision about how a number reads, taken in the one place
  // the plain-words tests cannot see.
  function renderColophon(meta) {
    document.getElementById('colophon-text').textContent = meta.colophon || '';
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
      // WORDS, not the task id. "predict:mlb" looks like English and is a
      // colon-joined key, which is the most dangerous kind of identifier to
      // leave on screen: it reads as though it were already plain.
      const label = el('strong', '', t.task_label || t.task);
      label.title = t.task;
      head.appendChild(label);
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

  // --- since you last looked ------------------------------------------------
  // Leads the page. The first question on opening a forecaster is not "what do
  // you think tonight" — it is "was I right last night".

  // THE FIFTH INSTANCE of the wrong-side defect lived on the line this
  // replaces: `'picked ' + String(s.subject).toUpperCase()`. On a moneyline
  // the subject is the HOME club, so every pick against the home side named
  // the team the model forecast AGAINST -- and it shouted the stored
  // identifier, so a prop read "FERNANDO TATIS JR. BATTER_HITS".
  //
  // It survived the guard that catches the other four because that guard reads
  // Python and this is JavaScript. The structural answer is the one the rest of
  // the interface already uses: the server writes the sentence, the renderer
  // places it. `s.phrase` comes from `language.phrase`, flip included.
  function settledRow(s) {
    const row = el('div', 'settled-row' + (s.correct ? ' win' : ' loss'));
    row.appendChild(el('span', 'settled-verdict', s.correct ? 'WIN' : 'LOSS'));
    row.appendChild(el('span', 'settled-match', s.matchup));
    row.appendChild(el('span', 'settled-pick', s.phrase || ''));
    const nums = el('span', 'settled-nums');
    nums.textContent = 'model ' + pct(shownProb(s), 1) +
      (s.market_prob === null || s.market_prob === undefined
        ? ' · no line' : ' · market ' + pct(s.market_prob, 1));
    row.appendChild(nums);
    if (s.final_score) row.appendChild(el('span', 'settled-score', s.final_score));
    // The same three sentences the expanded pick rows carry, so a resolved row
    // says WHY without having to be opened somewhere else.
    const sentences = (s.why && s.why.sentences) || [];
    if (sentences.length) {
      row.appendChild(el('p', 'settled-why', sentences.join(' ')));
    }
    return row;
  }

  function paintDigest(data, hosts) {
    const msg = hosts.msg;
    msg.innerHTML = '';
    if (data.n) {
      // Correct in green, wrong in plain chrome. Green is the positive value;
      // being wrong is not an alarm, it is half of a calibration record.
      msg.appendChild(document.createTextNode('Since you last looked: '));
      msg.appendChild(el('b', '', data.n + ' resolved'));
      msg.appendChild(document.createTextNode(' — '));
      msg.appendChild(el('span', 'up', data.correct + ' correct'));
      msg.appendChild(document.createTextNode(', ' + data.wrong + ' wrong'));
      if (data.brier !== null && data.brier !== undefined) {
        msg.appendChild(el('span', 'mono-inline', ' · Brier ' + num(data.brier, 4)));
      }
    } else {
      msg.textContent = data.headline;
    }

    const counts = hosts.countdown;
    if (counts) {
      counts.textContent = (data.movement.buckets[0] || {}).countdown ||
        (data.today && data.today.line) || '';
      counts.hidden = !counts.textContent;
    }

    // The strip owns the notice controls; renderNotices finds them by id.
    // Passing a host was how a second copy came to exist.
    renderNotices(data.warnings || []);

    if (hosts.settled) {
      hosts.settled.innerHTML = '';
      if (data.settled.length) {
        hosts.settled.appendChild(el('div', 'section-label', 'Resolved ' + data.scope));
        data.settled.forEach(s => hosts.settled.appendChild(settledRow(s)));
      }
      // RULING 1: a market the slate asked nothing in says so in words. A
      // silent absence reads as a failure to find questions and invites the
      // wrong repair -- adding rungs until the model is confident somewhere.
      const quiet = (data.today && data.today.quiet_markets) || [];
      quiet.forEach(line => {
        hosts.settled.appendChild(el('div', 'today-line quiet-market', line));
      });
      if (data.today && data.today.line) {
        hosts.settled.appendChild(el('div', 'today-line', data.today.line));
      }
    }
  }

  // ONE STRIP, and ONE IMPLEMENTATION OF IT.
  //
  // C2 was meant to collapse three stacked full-width notice boxes into a
  // single expandable line, and it half did: the markup carried a
  // `#notices-summary` button and a `#notices-detail` panel, and this function
  // ALSO built a summary button and a detail panel of its own inside the host.
  // Two implementations of one control. Which one a reader got depended on
  // which host the caller passed, so the notices collapsed on the front page
  // and stacked full-width everywhere else -- the regression the brief
  // describes, and it was invisible to every test because both versions
  // render something.
  //
  // Now: the markup owns the elements, this fills them, and there is nowhere
  // for a second version to live.
  function renderNotices(warnings) {
    const summary = document.getElementById('notices-summary');
    const detail = document.getElementById('notices-detail');
    if (!summary || !detail) return;

    if (!warnings.length) {
      summary.hidden = true;
      detail.hidden = true;
      detail.innerHTML = '';
      return;
    }

    summary.hidden = false;
    summary.innerHTML = '';
    summary.appendChild(el('b', 'notices-count',
      warnings.length + (warnings.length === 1 ? ' notice' : ' notices')));
    summary.appendChild(document.createTextNode(' \u25BE'));
    summary.title = warnings.map(shortNotice).join(' \u00B7 ');

    detail.innerHTML = '';
    detail.hidden = true;
    summary.setAttribute('aria-expanded', 'false');
    warnings.forEach(w => detail.appendChild(el('div', 'greet-warn ' + w.kind, w.text)));

    // Rebound rather than accumulated: renderNotices runs on every sport
    // switch, and addEventListener would stack a new handler each time, so the
    // panel would toggle twice and appear not to open at all.
    summary.onclick = () => {
      detail.hidden = !detail.hidden;
      summary.setAttribute('aria-expanded', String(!detail.hidden));
    };
  }

  // "predict:nfl never run", "NFL schedule stale 21h" — the key words only.
  function shortNotice(w) {
    // Keep the task's NAME. Splitting on the first colon turned "predict:nfl"
    // and "predict:nba" both into "predict", so the bar said "predict never
    // run · predict never run" — two notices that read as one repeated.
    const text = w.text || '';
    const head = text.split(': ')[0];
    if (w.kind === 'silent') return head + ' never run';
    if (w.kind === 'missed') return head + ' missed a slate';
    const hours = text.match(/([\d.]+)h ago/);
    return head + (hours ? ' stale ' + Math.round(+hours[1]) + 'h' : ' stale');
  }

  async function renderGreeting() {
    const strip = document.getElementById('glance');
    if (!strip) return;
    try {
      const data = await fetchJSON(withSport('/api/digest'));
      paintDigest(data, {
        msg: document.getElementById('greet-msg'),
        countdown: document.getElementById('greet-countdown'),
        warnings: null,          // the strip owns them now
        settled: null
      });
      strip.dataset.empty = 'false';
      // The route decided visibility before this fetch resolved, so re-apply
      // it rather than unhiding unconditionally -- otherwise the strip
      // reappears on whatever page the reader has since navigated to.
      applyRouteVisibility();
    } catch (err) {
      // Hidden rather than half-drawn, but NOT silent: a greeting that fails
      // quietly is a greeting that is wrong and looks fine.
      strip.hidden = true;
      strip.dataset.empty = 'true';
      console.error('greeting failed:', err);
    }
  }

  // The permanent page. Reads WITHOUT moving the marker, so a day can be
  // linked, shared and read twice.
  async function renderDigest() {
    const picker = document.getElementById('digest-day');
    // Defaults to TODAY rather than "since you last looked". The strip at the
    // top of the page moves the marker when it is read, so by the time anybody
    // opens this page that window is empty by construction — and an empty
    // permanent page is not a permanent page.
    if (picker && !picker.value) {
      picker.value = new Date().toISOString().slice(0, 10);
    }
    const day = picker && picker.value ? picker.value : null;
    const url = day
      ? withSport('/api/digest') + '&day=' + encodeURIComponent(day)
      : withSport('/api/digest') + '&peek=true';
    const data = await fetchJSON(url);

    document.getElementById('digest-caption').textContent =
      data.day ? data.day : 'since you last looked';

    const host = document.getElementById('digest-body');
    host.innerHTML = '';
    const strip = el('section', 'greet');
    const msg = el('div', 'msg');
    const countdown = el('div', 'countdown');
    strip.appendChild(msg);
    strip.appendChild(countdown);
    host.appendChild(strip);

    const warnings = el('div');
    const settled = el('div');
    host.appendChild(warnings);
    host.appendChild(settled);
    paintDigest(data, { msg, countdown, warnings, settled });

    if (!data.n && !data.day) {
      host.appendChild(el('div', 'footnote',
        'Pick a day above to read any past digest.'));
    }
  }

  // WHICH LAYOUT IS LIVE, on the body, so CSS can pin the page only when the
  // desk is actually on. Recomputed on resize because a window dragged across
  // 1280px must change layout, and the tiles and rows are different DOM --
  // a media query alone cannot swap them.
  function applyDeskClass() {
    document.body.classList.toggle('desk-on', isDesk() && state.view === 'week');
    placeGreeting();
  }

  let deskWasOn = null;
  window.addEventListener('resize', () => {
    applyDeskClass();
    const now = isDesk();
    if (deskWasOn !== null && now !== deskWasOn && state.view === 'week') {
      // Crossing the breakpoint changes which elements exist, not just how
      // they look, so the slate is rendered again rather than restyled.
      renderWeek();
    }
    deskWasOn = now;
  });
  document.addEventListener('keydown', deskKeys);

  const ROUTES = {
    record: renderRecord,
    week: renderWeek,
    factors: renderFactors,
    versions: renderVersions,
    history: renderHistory,
    schedule: renderSchedule,
    digest: renderDigest
  };

  // MERGING THE GREETING AND THE NOTICES PUT TWO RULES ON ONE ELEMENT, and
  // they disagree. "Since you last looked" belongs on the home tab: it is not
  // the question somebody browsing the factor registry is asking. A WARNING
  // belongs on every page, because a warning nobody sees is not a warning.
  //
  // So the strip survives off-home when it is carrying notices, and only the
  // greeting sentence goes quiet. Extracted into a function because the route
  // decides this BEFORE the digest fetch resolves, and the fetch used to
  // unhide the strip unconditionally afterwards -- so it reappeared on
  // whatever page the reader had since navigated to.
  function applyRouteVisibility() {
    const home = (state.view || 'record') === 'record';
    const greeting = document.getElementById('glance');
    if (greeting) {
      const notices = document.getElementById('notices-summary');
      const hasNotices = notices && !notices.hidden;
      const msg = document.getElementById('greet-msg');
      if (msg) msg.hidden = !home;
      greeting.hidden = (!home || greeting.dataset.empty === 'true') && !hasNotices;
      greeting.classList.toggle('glance-notices-only', !home && hasNotices);
    }
    const settled = document.getElementById('greet-settled');
    if (settled) settled.hidden = !home;
  }

  async function route() {
    clearError();
    const name = (location.hash.replace('#/', '') || 'record');
    const view = ROUTES[name] ? name : 'record';
    document.querySelectorAll('.view').forEach(v => { v.hidden = true; });
    // The strip leads the FRONT page. On the digest route the same content is
    // the page itself, and showing both put two identical panels on screen.
    // ONE PAGE GREETS; EVERY PAGE WARNS. The since-you-last-looked strip is a
    // home-tab thing - it answers "what happened while I was away", which is
    // not the question somebody browsing the factor registry is asking. The
    // notice bar stays on every page, because a warning nobody sees is not a
    // warning.
    state.view = view;
    applyRouteVisibility();
    applyDeskClass();
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
      await renderRecordLine();
      await renderGreeting();
      state.meta = await fetchJSON(withSport('/api/meta'));
      renderBanner(state.meta);
      renderColophon(state.meta);
      state.scorecard = await fetchJSON(withSport('/api/scorecard'));
      await loadMarkets();
      await loadWeekPicker();
    } catch (err) {
      showError(err);
    }

    wireSortToggle();
    const dayPicker = document.getElementById('digest-day');
    if (dayPicker) dayPicker.addEventListener('change', () =>
      renderDigest().catch(showError));
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
