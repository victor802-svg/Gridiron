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
                  markets: ['spread'], historyOffset: 0, historyTotal: 0,
    // WHICH DAY THE CALENDAR HAS SELECTED, or null for the whole season.
    // Declared here rather than left to spring into existence on first click:
    // an undefined that behaves like null until it does not is the kind of
    // state nobody can reason about.
    calendarDay: null,
    // THE CARDS UI (2026-09-04). Declared here for the reason the note above
    // gives: an undefined that behaves like a default until it does not is
    // state nobody can reason about.
    //
    // `market` is the selected market TAB, empty for "All". `showAllCards` is
    // whether the grid has been expanded past its first six, and it resets on
    // every slate, sport, sort and tab change -- a grid left expanded across a
    // filter change shows a different number of cards than the control says.
    market: '' };

  // ONE ANSWER PER QUESTION ASKED (UI audit finding 1, 2026-09-05).
  //
  // Every request here carries the sport, and every answer used to paint the
  // moment it arrived -- whichever order that was. College football's 243
  // cards answer slowest, so a reader who clicked NCAAF and then UFC within a
  // second got UFC's tabs over NCAAF's cards; the NBA tab, empty, showed 243
  // football picks under "Today". Two sequence numbers end it: `sportSeq`
  // moves on every sport switch, `weekSeq` on every slate render, and a
  // loader that took its number before asking checks it after the answer
  // and paints nothing if the number has moved on. `audit.render_guard_faults`
  // reads every sport-scoped fetch and refuses one that paints unchecked.
  let sportSeq = 0;
  let weekSeq = 0;
  function stale(seq) { return seq !== sportSeq; }

  function withSport(path, extra) {
    const p = new URLSearchParams(extra || {});
    p.set('sport', state.sport);
    return path + (path.includes('?') ? '&' : '?') + p.toString();
  }

  async function fetchJSON(url) {
    let res;
    try {
      res = await fetch(url);
    } catch (err) {
      // THE NETWORK'S OWN WORDS ARE NOT WORDS (UI audit finding 8,
      // 2026-09-05). "Failed to fetch" is what the browser says; the sentence
      // shown is the server's, handed over at boot, with the offline bar's
      // own text as the fallback before boot has finished.
      const line = (state.meta && state.meta.unreachable_line) ||
        ((document.getElementById('offline-bar') || {}).textContent || '').trim();
      throw new Error(line || String(err));
    }
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
      // NOT GREEN AND RED (GRIDIRON_16 R2). This drew the inside-band points
      // green and the rest red until 2026-09-02, which read as "these buckets
      // won" -- and under the colour law green means a PICK won and nothing
      // else. A calibrated bucket is not a won pick.
      //
      // The encoding is EMPHASIS instead, and it points the right way round:
      // a bucket sitting inside the band is the expected state and is drawn
      // quietly, while one outside it is what the reader came to find and is
      // drawn in full chrome. The old colouring made the unremarkable points
      // the loudest thing on the chart.
      const inside = Math.abs(b.actual - b.claimed) <= ACCEPTABLE;
      ctx.fillStyle = inside ? css('--muted') : css('--chrome');
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
    // TWO FORECASTERS, ONE AT A TIME. The selector swaps which table is
    // shown; there is no option that shows both at once, because the only
    // thing a combined table could report is a merge. (A third, the
    // operator's own informed calls, stood here until 2026-09-02.)
    renderForecasterPicker(sc);
    renderTierTable(sc.tier_table);
    // THE MODEL SECTION IS PART OF THIS PAGE NOW (P5): the calibration
    // chart, the factor cards and the dated "what changed, when" timeline.
    renderFactors().catch(showError);
    renderVersions().catch(showError);
    // CALLED WITH THE WHOLE SCORECARD, not smuggled through the tier table:
    // the corrections, the drift pairs and the read windows are siblings of
    // that table, not part of it.
    renderOtherGates(sc);
    renderAtTheLine(sc);
    renderRanker(sc);
    renderPriced(sc);
    renderLearning().catch(showError);
    loadTierMarkets((sc.tier_table || {}).prop_type ||
                    (sc.tier_table || {}).market_type);
    const tierSel = document.getElementById('tier-market');
    const shownMarket = (sc.tier_table || {}).prop_type || (sc.tier_table || {}).market_type;
    if (tierSel && (tierSel.value !== shownMarket ||
                    forecasterChoice !== ((sc.tier_table || {}).predictor || 'statistical'))) {
      refreshTierTable().catch(showError);
    }
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
    const seq = sportSeq;
    const data = await fetchJSON(withSport('/api/over-time?' + params.toString()));
    if (stale(seq)) return;
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
    const cell = el('div', 'cat-cell' + (c.retired ? ' retired' : ''));
    // categoryLabel returns a STRING, not a node.
    cell.appendChild(el('div', '', categoryLabel(c)));
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
  //: Which forecaster's table the Record tab is showing. Memory only, and
  //: deliberately not remembered across sessions: a reader returning to the
  //: page should see the model's record, not whichever table they left open.
  let forecasterChoice = 'statistical';

  function renderForecasterPicker(sc) {
    const host = document.getElementById('forecaster-picker');
    if (!host) return;
    host.innerHTML = '';
    (sc.forecasters || []).forEach(f => {
      const b = el('button', '', f.label);
      b.type = 'button';
      b.dataset.forecaster = f.forecaster;
      b.setAttribute('aria-pressed', String(f.forecaster === forecasterChoice));
      b.addEventListener('click', () => {
        forecasterChoice = f.forecaster;
        renderForecasterPicker(sc);
        refreshTierTable().catch(showError);
      });
      host.appendChild(b);
    });
    // THE INFORMED-FORECASTER NOTE went with the operator's calls
    // (GRIDIRON_16 R1). It said, under the operator's own table, that those
    // forecasts had seen the model and the market first. No forecaster is
    // informed any more, so the note could only ever be empty -- and it read
    // from `operator_tier_table`, a payload key that no longer exists.
  }

  // HOW CLOSE A GATE IS (GRIDIRON_13 P1). ONE COMPONENT, used by the tier
  // rows, the correction gates, the drift pairs and the dated read windows.
  // A second implementation would be a second opinion about what "close"
  // means, and they would disagree the first time a gate moved.
  //
  // The words are the SERVER'S -- `language.progress` writes the line and the
  // note. This draws a bar from the two counts and places the text. It
  // computes no share of its own: the width is a geometry, not a figure, and
  // the figures on the page are the counts beside it.
  function gateLine(p) {
    const wrap = el('div', 'gate');
    if (!p) return wrap;
    const bar = el('div', 'gate-bar');
    const fill = el('i');
    // CHROME ON HAIRLINE, never green: a filling bar is not a win (R2).
    fill.style.width = (p.needed
      ? Math.max(0, Math.min(100, (p.done / p.needed) * 100))
      : 0) + '%';
    bar.appendChild(fill);
    wrap.appendChild(bar);
    const words = el('div', 'gate-words');
    words.appendChild(el('b', '', p.line || ''));
    if (p.note) words.appendChild(el('span', '', ' · ' + p.note));
    wrap.appendChild(words);
    return wrap;
  }

  // EVERY OTHER GATE ON THE PAGE, through the same component. The
  // corrections need 50 settled before one is fitted; the drift question
  // needs 50 pairs before a direction is reported; a dated window opens on a
  // day. All three used to state only that they had not been reached.
  function renderOtherGates(sc) {
    const host = document.getElementById('other-gates-list');
    const panel = document.getElementById('other-gates');
    const count = document.getElementById('other-gates-n');
    if (!host || !panel) return;
    host.innerHTML = '';
    // NAMED BY THE SERVER. These names were glued together here -- a label
    // plus a market field -- until `check_js_composes_no_prose` refused it on
    // the first gate run. `language.gate_name` writes them now.
    const entries = (sc && sc.gates) || [];
    entries.forEach(e => {
      const row = el('div', 'gate-row');
      row.appendChild(el('div', 'gate-name', e.name));
      row.appendChild(gateLine(e.progress));
      if (e.why) row.appendChild(el('div', 'gate-why', e.why));
      host.appendChild(row);
    });
    if (count) count.textContent = entries.length + ' gates';
    panel.hidden = entries.length === 0;
  }

  // WHAT THE RECORD HAS TAUGHT IT (T3, 2026-09-07). Fetched on its own route
  // because it reads two modules the slate does not touch. Every sentence is
  // the server's; this places them.
  async function renderLearning() {
    const panel = document.getElementById('learning');
    const host = document.getElementById('learning-list');
    if (!panel || !host) return;
    const seq = sportSeq;
    const data = await fetchJSON(withSport('/api/learning', {}));
    if (stale(seq)) return;
    host.innerHTML = '';
    requireN(data, 'what the record has taught it');
    const note = document.getElementById('learning-note');
    if (note) note.textContent = data.note || '';
    const never = document.getElementById('learning-never');
    if (never) never.textContent = data.never_rewrites || '';
    const refit = document.getElementById('learning-refit');
    if (refit) refit.textContent = data.last_refit ? data.last_refit.slice(0, 10) : '';
    (data.categories || []).forEach(entry => {
      requireN(entry, 'the correction for "' + entry.market + '"');
      const row = el('div', 'gate-row');
      row.appendChild(el('div', 'gate-name', entry.market_label));
      row.appendChild(el('div', 'gate-why', entry.status_words));
      row.appendChild(el('div', 'gate-why', entry.meaning_words));
      if (entry.drift_words) row.appendChild(el('div', 'gate-why', entry.drift_words));
      host.appendChild(row);
    });
    panel.hidden = (data.categories || []).length === 0;
  }

  // THE PRICED RECORD (THE_PRICED, 2026-09-07). Placed, never composed. Three
  // lists that are deliberately separate: what may be priced at all, what the
  // closing line says about what was, and the two forecasters' scores on the
  // same questions -- side by side, never summed, because a priced forecaster
  // with a better Brier score is mostly reporting the market's skill.
  function renderPriced(sc) {
    const panel = document.getElementById('priced-record');
    const coverage = document.getElementById('coverage-list');
    const clv = document.getElementById('clv-list');
    const scores = document.getElementById('priced-list');
    if (!panel || !coverage || !clv || !scores) return;
    coverage.innerHTML = '';
    clv.innerHTML = '';
    scores.innerHTML = '';
    const cov = (sc && sc.coverage) || null;
    const line = (sc && sc.closing_line) || null;
    const priced = (sc && sc.priced) || null;
    if (!cov && !line && !priced) { panel.hidden = true; return; }

    const version = document.getElementById('priced-version');
    if (version && priced) version.textContent = priced.blend_version || '';
    const words = document.getElementById('coverage-words');
    if (words && cov) words.textContent = cov.words || '';
    const note = document.getElementById('priced-note');
    if (note && priced) note.textContent = priced.note || '';

    if (cov) {
      requireN(cov, 'the coverage measurement');
      (cov.entries || []).forEach(entry => {
        requireN(entry, 'coverage of "' + entry.market + '"');
        const row = el('div', 'gate-row');
        row.appendChild(el('div', 'gate-name', marketLabel(entry.market)));
        row.appendChild(el('div', 'gate-why', entry.why));
        coverage.appendChild(row);
      });
      (cov.stopped || []).forEach(stop => {
        requireN(stop, 'a stopped market');
        const row = el('div', 'gate-row');
        row.appendChild(el('div', 'gate-name', marketLabel(stop.market)));
        row.appendChild(el('div', 'gate-why', stop.why));
        coverage.appendChild(row);
      });
    }

    if (line) {
      requireN(line, 'the closing line');
      (line.markets || []).forEach(entry => {
        requireN(entry, 'the closing line for "' + entry.market + '"');
        const row = el('div', 'gate-row');
        row.appendChild(el('div', 'gate-name', marketLabel(entry.market)));
        row.appendChild(el('div', 'gate-why', entry.words));
        if (entry.finding) row.appendChild(el('div', 'gate-why', entry.finding));
        clv.appendChild(row);
      });
    }

    if (priced) {
      requireN(priced, 'the priced forecaster');
      (priced.categories || []).forEach(entry => {
        requireN(entry, 'the priced curve for "' + entry.market + '"');
        const row = el('div', 'gate-row');
        row.appendChild(el('div', 'gate-name', marketLabel(entry.market)));
        row.appendChild(el('div', 'gate-why', entry.gate_line));
        scores.appendChild(row);
      });
    }
    panel.hidden = false;
  }

  // DID THE ORDERING EARN ITS PLACE (S3, 2026-09-07). The shortlist is a
  // claim of a kind -- that these were the better questions -- and this is
  // where it is checked. Two counts per market and, once both sides pass the
  // gate, one sentence that is allowed to say the ordering separated nothing.
  function renderRanker(sc) {
    const panel = document.getElementById('ranker-record');
    const host = document.getElementById('ranker-list');
    const note = document.getElementById('ranker-note');
    const version = document.getElementById('ranker-version');
    if (!panel || !host) return;
    host.innerHTML = '';
    const rank = (sc && sc.ranker) || null;
    if (!rank) { panel.hidden = true; return; }
    if (note) note.textContent = rank.note || '';
    if (version) version.textContent = rank.ranker_version || '';
    (rank.comparisons || []).forEach(c => {
      requireN(c, 'ranker comparison "' + c.market + '"');
      requireN(c.shortlisted, 'shortlisted side of "' + c.market + '"');
      requireN(c.not_shortlisted, 'outranked side of "' + c.market + '"');
      const row = el('div', 'gate-row');
      row.appendChild(el('div', 'gate-name', marketLabel(c.market)));
      row.appendChild(el('div', 'gate-why', c.gate_line));
      if (c.verdict) row.appendChild(el('div', 'gate-why', c.verdict));
      host.appendChild(row);
    });
    panel.hidden = (rank.comparisons || []).length === 0;
  }

  // TODAY (CARD_FACE, 2026-09-07, replacing T1's rows).
  //
  // ONE CARD DESIGN FOR BOTH GROUPS; the heading says which group, not the
  // card. The three prices read across in the order a reader needs them --
  // what the model makes it, what the venue is at, what the difference is
  // worth after the fee -- and the third is the largest thing on the card
  // because it is the only one that decides anything.
  //
  // THIS FUNCTION WAS DEFINED TWICE, identically, one copy directly after the
  // other. The second replaced the first at load; a fix applied to the wrong
  // one would have changed nothing on the screen and looked like a mystery.
  // `audit.duplicate_js_definitions` now fails on that shape.
  //
  // EVERY STRING HERE IS THE SERVER'S, labels included. The one thing worked
  // out in the browser is a kickoff instant turned into the reader's own
  // clock, because the browser is the only party that knows the timezone --
  // and it is a TIME, never a countdown. A countdown is a sportsbook's
  // pressure rather than its grammar and is banned by name.
  // ONE CARD, THREE STATES (THREE_STATES S2, 2026-09-08).
  //
  // Upcoming carries the matchup and the prices. Live carries the score and
  // nothing that could be acted on. Final carries the outcome against the
  // number the card was opened with, which is the whole argument for keeping
  // one card through three states rather than three pages.
  //
  // EVERY STRING IS THE SERVER'S, labels included. The one thing worked out
  // here is a kickoff instant turned into the reader's own clock, because the
  // browser is the only party that knows the timezone -- and it is a TIME,
  // never a countdown.
  //
  // THE COLOUR IS STRUCTURAL AND IS NOT A VERDICT. A club's own colour marks
  // its own name; the payout chip takes the colour of the side the question
  // names. `audit.check_the_colour_law` still rules that green means a pick
  // won and red that one lost, and neither appears here: the edge line is the
  // only place either can.
  function clubPill(name, colours) {
    const pill = el('span', 'club');
    pill.textContent = name || '';
    if (colours && colours.on_white) {
      pill.style.background = '#' + colours.on_white;
    }
    return pill;
  }

  function todayCard(entry, labels) {
    requireN(entry, 'a card on today');
    const state = entry.state || 'upcoming';
    const face = el('article', 'face face-' + state + (entry.taken ? ' face-took' : ''));
    // THE ID THE LIVE TICK FINDS IT BY. `applyLive` patches the score on a
    // card already on screen rather than rebuilding the slate under a reader
    // (audit.live_update_faults), and it needs a handle to patch.
    if (entry.prediction_id !== undefined) face.dataset.id = entry.prediction_id;
    if (entry.favoured_colour) {
      face.style.setProperty('--club', '#' + entry.favoured_colour);
    }

    // --- the band -----------------------------------------------------
    const head = el('header', 'face-event');
    const band = el('div', 'face-band');
    band.appendChild(clubPill(entry.away_name || entry.away, entry.away_colour));
    band.appendChild(el('span', 'face-at', entry.matchup ? '' : ''));
    band.appendChild(clubPill(entry.home_name || entry.home, entry.home_colour));
    head.appendChild(band);

    const when = el('span', 'face-when');
    if (state === 'live') {
      // THE SCORE WHERE THE START TIME WAS, and the time of the last poll
      // beside it: a score with no timestamp is a score a reader trusts too
      // much, and the poller runs only while a window is open.
      when.appendChild(el('span', 'face-score', entry.score_words || ''));
      when.appendChild(el('span', 'face-period', entry.period_words || ''));
      when.appendChild(el('span', 'face-polled', entry.polled_words || ''));
    } else if (state === 'final') {
      when.appendChild(el('span', 'face-score', entry.score_words || ''));
    } else if (entry.kickoff_utc) {
      when.appendChild(el('span', 'face-when-label', entry.kickoff_label || ''));
      when.appendChild(el('time', 'face-time', localTime(entry.kickoff_utc)));
    }
    head.appendChild(when);

    // THE SPORT'S COLOUR IS THE STYLESHEET'S, chosen by a class rather than
    // set inline, so `tools/contrast.py` can read it off `:root` and measure
    // it. A hex in two files is two colours that will disagree.
    const tag = el('span', 'face-sport sport-' + (entry.sport_key || ''),
                   entry.sport_label || '');
    head.appendChild(tag);
    if (entry.taken_badge) head.appendChild(el('span', 'face-yours', entry.taken_badge));
    face.appendChild(head);

    face.appendChild(el('div', 'face-q', entry.question || ''));

    // --- what the record already knew about this game ------------------
    const context = el('div', 'face-context');
    const line = (words) => {
      if (!words) return;
      context.appendChild(el('span', 'face-fact', words));
    };
    if (entry.away_starter || entry.home_starter) {
      line(entry.away_starter);
      line(entry.home_starter);
    }
    // FORM IS READ AT A GLANCE OR NOT AT ALL (operator, 2026-09-08). The
    // last five results arrived as one grey run of letters and a reader had
    // to spell them out. W is green and L is red -- the record's own two
    // colours, doing the one job the law gives them, on a CLUB'S GAME rather
    // than on a pick. A draw is neither, so it stays the colour of the line.
    //
    // Anything that is not a run of W/L/D is not a streak: "no finished
    // games yet" is a sentence and renders as one.
    const formLine = (words) => {
      if (!words) return;
      const marks = words.split(' ');
      if (!marks.every(m => m === 'W' || m === 'L' || m === 'D')) {
        line(words);
        return;
      }
      const fact = el('span', 'face-fact face-form');
      marks.forEach(m => fact.appendChild(el(
        'span', m === 'W' ? 'fmark win' : m === 'L' ? 'fmark loss' : 'fmark',
        m)));
      context.appendChild(fact);
    };
    formLine(entry.away_form ? entry.away_form : null);
    formLine(entry.home_form ? entry.home_form : null);
    line(entry.weather_words);
    if (context.childNodes.length) face.appendChild(context);

    // --- the prices, on states that may carry them ---------------------
    if (state === 'upcoming') {
      const prices = el('div', 'face-prices');
      const box = (cls, label, value) => {
        const b = el('div', cls);
        b.appendChild(el('span', 'box-label', label));
        b.appendChild(el('span', 'box-value', value));
        return b;
      };
      prices.appendChild(box('box', labels.model, entry.model_words));
      // THE PAYOUT IS THE BIG CHIP (operator ruling, 2026-09-08), filled in
      // the colour of the side the question names, with the price beneath it.
      const payout = box('box box-payout', labels.venue, entry.payout_words);
      // THE CLUB'S COLOUR ONLY WHEN THERE IS A PAYOUT TO COLOUR (2026-09-08).
      // A card with no venue price was painting "no price yet" on the
      // favoured club's colour, and on a club whose colour is red that reads
      // as a verdict: the operator reported it as red, and the colour law
      // keeps red for a loss. With no number in it the chip is grey, and
      // `box-payout-empty` says so rather than borrowing a team's identity
      // for an absence.
      if (entry.payout !== null && entry.payout !== undefined &&
          entry.favoured_colour) {
        payout.style.background = '#' + entry.favoured_colour;
      } else {
        payout.classList.add('box-payout-empty');
      }
      // THE OPENING READ, WITH ITS TIME (GRIDIRON_OPENING_READ, 2026-09-09).
      // The words are the server's; the instant is turned into the reader's
      // own clock here, the same way the kickoff line has always worked. A
      // price with no "read at" beside it gets compared with an edge that was
      // measured at kickoff, which is the one mistake this line prevents.
      if (entry.open_read_words && entry.open_read_utc) {
        const w = entry.open_read_words;
        payout.appendChild(el(
          'span', 'box-under',
          w.before + ' ' + localTime(entry.open_read_utc) + ' \u00b7 ' + w.after));
      } else {
        payout.appendChild(el('span', 'box-under', entry.price_words || ''));
      }
      prices.appendChild(payout);
      face.appendChild(prices);

      // THE EDGE IS ONE QUIET LINE, and the only green or red on the card.
      const edge = el('div', 'face-edge ' + (entry.edge_state || 'none'));
      edge.appendChild(el('span', 'edge-label', entry.edge_label || labels.edge));
      edge.appendChild(el('span', 'edge-value', entry.edge_line_words || ''));
      face.appendChild(edge);

      if (entry.size_words) face.appendChild(el('div', 'face-size', entry.size_words));
    }
    if (state === 'final' && entry.settled_words) {
      face.appendChild(el('div', 'face-settled', entry.settled_words));
    }

    const meta = el('div', 'face-meta');
    meta.appendChild(el('span', 'face-gate', entry.gate_words || ''));
    if (entry.tier_chip) meta.appendChild(el('span', 'chip', entry.tier_chip));
    face.appendChild(meta);

    // WHAT IS KNOWN ABOUT THIS MARKET'S METHOD, ON THE FACE AND NOT ONE TAP
    // IN (operator ruling 2, 2026-09-04). The old grid card rendered this and
    // the CARD_FACE card never did, so when the grid was removed on
    // 2026-09-08 the caveat stopped reaching the reader altogether -- the
    // payload carried it and nothing drew it. Caught by
    // `test_the_flagged_note_is_readable_without_a_tap`, which is the test
    // that exists for exactly this.
    //
    // A caveat behind a tap is a caveat most readers never reach, and the
    // reader taking the percentage at face value is the one it is written for.
    if (entry.method_note) {
      face.appendChild(el('p', 'face-method', entry.method_note));
    }

    // THE FIRST SENTENCE WITHOUT A CLICK, the rest behind Why.
    if (entry.first_sentence) {
      face.appendChild(el('p', 'face-lede', entry.first_sentence));
    }

    const actions = el('div', 'face-actions');
    // A LIVE CARD CARRIES NO TAP. Its game is being played; there is nothing
    // to decide and nothing on the card to decide it with.
    if (state === 'upcoming') {
      const mark = el('button', 'took' + (entry.taken ? ' took-done' : ''));
      mark.type = 'button';
      mark.textContent = entry.taken ? labels.taken : labels.took;
      mark.disabled = !!entry.taken;
      mark.onclick = async () => {
        mark.disabled = true;
        await fetch('/api/taken/' + entry.prediction_id, {
          method: 'POST',
          headers: { 'X-Gridiron-Form': csrfToken || '' },
        });
        renderWeek().catch(showError);
      };
      actions.appendChild(mark);
    }

    const sentences = (entry.why && entry.why.sentences) || [];
    if (sentences.length || entry.reasoning || entry.rail_line ||
        (entry.top_factors || []).length) {
      const more = el('button', 'expand');
      more.type = 'button';
      more.textContent = labels.why;
      more.setAttribute('aria-expanded', 'false');
      const body = el('div', 'face-why');
      body.hidden = true;
      // MODEL, MARKET AND GAP AS TEXT (R3), first in the body. A dot-and-span
      // graphic stood here until 2026-09-02 and made the reader estimate two
      // percentages off a 100-pixel track. It was rendered by the old card's
      // body, which the grid took with it on 2026-09-08.
      if (entry.rail_line) {
        body.appendChild(el('p', 'face-numbers', entry.rail_line));
      }
      if (sentences.length) {
        sentences.forEach(s => body.appendChild(el('p', 'face-sentence', s)));
      } else if (entry.reasoning) {
        body.appendChild(el('p', 'face-sentence', entry.reasoning));
      }
      const chips = factorChips(entry);
      if (chips) body.appendChild(chips);
      // THE WAY OUT TO THE WORKINGS. The coefficient table moved to the
      // Factors page (R1) and the old card's body carried this link to it;
      // the CARD_FACE card never did, so removing the grid on 2026-09-08 left
      // the card's reasons with no route to the page that explains them.
      const w = entry.why || {};
      const moreLink = el('a', 'face-more',
        (w.more_label || 'How the model works') + ' →');
      moreLink.href = w.more_href || '#/factors';
      body.appendChild(moreLink);
      more.onclick = () => {
        body.hidden = !body.hidden;
        more.setAttribute('aria-expanded', body.hidden ? 'false' : 'true');
      };
      actions.appendChild(more);
      face.appendChild(actions);
      face.appendChild(body);
      return face;
    }
    face.appendChild(actions);
    return face;
  }

  // THE VENUE'S PACKAGES (GRIDIRON_COMBOS C6, 2026-09-08).
  //
  // The app grades what the venue assembled; it never assembles one, and there
  // is no control here that adds a leg, builds anything, or invites another
  // selection. The only control is the same one a single card has: a record of
  // what the operator took.
  function comboCard(entry, labels) {
    const face = el('article', 'face combo-face');
    if (entry.accent) face.style.setProperty('--accent', '#' + entry.accent);

    // THE LEGS, AS THE VENUE WROTE THEM, each in its club's own colour. The
    // same pill the single card uses: a club's colour marks its own name and
    // is never a verdict.
    // `face-band` IS THE ROW THE SINGLE CARD PUTS ITS CLUBS IN, and it is the
    // row that has the gap between them. The first version invented
    // `face-clubs`, which no stylesheet knows, so the two legs rendered
    // welded together: "Chicago Cubs moneylineSan Francisco Giants moneyline".
    const clubs = el('div', 'face-band combo-legs');
    (entry.legs || []).forEach(leg => {
      clubs.appendChild(clubPill(leg.words, {on_white: leg.colour}));
    });
    face.appendChild(clubs);

    // THE PRICES, in the card grammar the rest of this page uses: the payout
    // is the big chip, with the price beneath it.
    const prices = el('div', 'face-prices');
    const box = (cls, label, value) => {
      const b = el('div', cls);
      b.appendChild(el('span', 'box-label', label));
      b.appendChild(el('span', 'box-value', value));
      return b;
    };
    prices.appendChild(box('box', labels.model, entry.fair_words || ''));
    const payout = box('box box-payout', labels.venue, entry.payout_words);
    if (entry.accent) payout.style.background = '#' + entry.accent;
    payout.appendChild(el('span', 'box-under', entry.price_words || ''));
    prices.appendChild(payout);
    face.appendChild(prices);

    // WHAT ITS OWN LEGS MULTIPLY TO, beside what the venue charges for them:
    // the venue's margin, or its discount, as one visible number.
    face.appendChild(el('p', 'combo-margin', entry.margin_words || ''));

    const edge = el('div', 'face-edge ' + (entry.edge_state || 'none'));
    edge.appendChild(el('span', 'edge-label', labels.edge));
    edge.appendChild(el('span', 'edge-value', entry.edge_words || ''));
    face.appendChild(edge);

    if (entry.size_words) face.appendChild(el('div', 'face-size', entry.size_words));

    const meta = el('div', 'face-meta');
    meta.appendChild(el('span', 'face-gate', entry.gate_words || ''));
    face.appendChild(meta);

    // THE COST, ON EVERY CARD. A package's fee per dollar is 1.7 to 2.8 times
    // the same legs taken singly, measured, and a card showing only its own
    // edge would be arguing one side.
    if (entry.singles_words) {
      face.appendChild(el('p', 'combo-singles', entry.singles_words));
    }

    const actions = el('div', 'face-actions');
    const mark = el('button', 'took' + (entry.taken ? ' took-done' : ''));
    mark.type = 'button';
    mark.textContent = entry.taken ? labels.taken : labels.took;
    mark.disabled = !!entry.taken;
    mark.onclick = () => takePackage(entry.package_id, mark, labels);
    actions.appendChild(mark);
    face.appendChild(actions);
    return face;
  }

  function takePackage(packageId, button, labels) {
    button.disabled = true;
    // `X-Gridiron-Form` IS THIS APP'S CSRF HEADER. The first version sent
    // `X-Gridiron-CSRF`, which the route refuses -- a 403 nobody could have
    // seen, because no package had ever rendered a button to press.
    fetch('/api/taken/package/' + packageId, {
      method: 'POST',
      headers: { 'X-Gridiron-Form': csrfToken || '' },
    }).then(r => r.json()).then(result => {
      if (result && result.taken) {
        button.textContent = labels.taken;
        button.classList.add('took-done');
      } else {
        button.disabled = false;
        if (result && result.why) button.title = result.why;
      }
    }).catch(() => { button.disabled = false; });
  }

  // A COMBO THE APP PUTS FORWARD (ruled 2026-09-09).
  //
  // NO PAYOUT CHIP, NO EDGE, NO VENUE PRICE, and their absence is the design.
  // The venue quotes a combo only to an account holder who asks; this app has
  // no account and LAW 5 does not permit one, so any price on this card would
  // be invented. What it carries is the half the app can do honestly -- what
  // the combo is worth -- and the line that turns that into a decision.
  function proposalCard(entry, labels) {
    const face = el('article', 'face combo-face');

    const head = el('div', 'face-head');
    (entry.legs || []).forEach((leg, i) => {
      if (i) head.appendChild(el('span', 'combo-and', '+'));
      head.appendChild(el('span', 'combo-leg', leg.words || ''));
    });
    face.appendChild(head);

    const prices = el('div', 'face-prices');
    const box = (cls, label, value) => {
      const b = el('div', cls);
      b.appendChild(el('span', 'box-label', label));
      b.appendChild(el('span', 'box-value', value));
      return b;
    };
    prices.appendChild(box('box', (labels && labels.model) || 'WORTH',
                           entry.fair_words || ''));
    // THE CEILING IS THE BIG NUMBER, because it is the only one on the card
    // that answers a question. The fair value is what it is worth; this is
    // what a reader may pay for it.
    const ceiling = box('box box-payout box-payout-empty', 'PAY BELOW',
                        entry.ceiling_words || '');
    prices.appendChild(ceiling);
    face.appendChild(prices);

    if (entry.size_words) face.appendChild(el('div', 'face-size', entry.size_words));
    if (entry.singles_words) {
      face.appendChild(el('p', 'face-sentence', entry.singles_words));
    }
    return face;
  }

  function renderCombos(combos, labels) {
    const host = document.getElementById('today-combos');
    const heading = document.getElementById('combos-heading');
    const counts = document.getElementById('combos-counts');
    const fee = document.getElementById('combos-fee');
    const empty = document.getElementById('combos-empty');
    if (!host) return;
    host.innerHTML = '';
    const data = combos || null;
    if (heading) heading.textContent = data ? (data.heading || '') : '';
    // THE SENTENCE THAT REPLACED "no package open" (ruled 2026-09-09). The
    // venue quotes a combo to an account holder on request and this app has
    // no account, so the group says what it can do and what it cannot -- it
    // never reports the venue as having nothing.
    if (counts) counts.textContent = data ? (data.rfq_words || '') : '';
    // THE COST SENTENCE BELONGS TO THE CARDS. It says every card prints both
    // rates, so above an empty group it describes cards that do not exist --
    // which is how a page starts teaching a reader to skip its own sentences.
    if (fee) {
      const cardsPresent = !!(data && data.cards && data.cards.length);
      fee.textContent = cardsPresent ? (data.fee_words || '') : '';
      fee.hidden = !cardsPresent;
      fee.dataset.emptyHidden = cardsPresent ? 'false' : 'true';
    }
    (data && data.cards ? data.cards : []).forEach(
      entry => host.appendChild(proposalCard(entry, labels)));
    // WHY THIS PRODUCT HAS NO SAMPLE SIZE, said beside the cards that carry
    // none. Every other number on this page arrives with its N; a reader who
    // has been taught that will look for one here and must be told instead of
    // left to wonder.
    if (data && data.cards && data.cards.length && data.unmeasurable_words) {
      host.appendChild(el('p', 'group-note', data.unmeasurable_words));
    }
    if (empty) {
      empty.textContent = (data && data.empty_words) || '';
      // HIDDEN BY ITS OWN EMPTINESS, which the tab logic then respects: the
      // sentence shows when there are no cards, and never beside them.
      const show = !!(data && data.empty_words);
      empty.hidden = !show;
      empty.dataset.emptyHidden = show ? 'false' : 'true';
    }
  }

  // WHICH TAB IS BEING LOOKED AT. The default is Upcoming; a reader who
  // switches to Live stays there across a refresh, because a poll that moved
  // them back would take the screen away from the game they are watching.
  let stateTab = 'upcoming';

  function applyStateTab() {
    const tabs = document.getElementById('state-tabs');
    // THE HEADS, NOT JUST THE HEADINGS (2026-09-08). This listed the heading
    // SPANS and not the `<h3>` rows they sit in, so switching to Live left
    // the clears group's coloured rule and its tier chip standing over an
    // empty tab -- a "SOLID" heading with nothing under it, which is what the
    // operator saw.
    const upcomingParts = ['clears-head-row', 'today-clears-heading',
                           'today-clears', 'today-fold',
                           'today-below-floor', 'watching-head-row',
                           'today-watching-heading', 'today-watching',
                           // COMBOS IS AN UPCOMING GROUP (C6). Nothing is
                           // sized in-game, so a package has nothing to say
                           // on Live and is a settled row rather than a card
                           // on Results.
                           'combos-heading-row', 'combos-counts', 'combos-fee',
                           'today-combos', 'combos-empty'];
    const livePresent = (document.getElementById('today-live') || {}).childNodes;
    const liveCount = livePresent ? livePresent.length : 0;
    if (tabs) {
      tabs.querySelectorAll('button').forEach(button => {
        const on = button.dataset.state === stateTab;
        button.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    }
    const show = (id, on) => {
      const node = document.getElementById(id);
      if (node) node.hidden = !on;
    };
    const upcoming = stateTab === 'upcoming';
    upcomingParts.forEach(id => {
      const node = document.getElementById(id);
      if (!node) return;
      if (upcoming) {
        // A group hidden by its own emptiness stays hidden; this only takes
        // the tab's word for it.
        if (node.dataset.emptyHidden !== 'true') node.hidden = false;
      } else {
        node.hidden = true;
      }
    });
    show('live-heading-row', !upcoming && liveCount > 0);
    show('today-live', !upcoming && liveCount > 0);
    show('live-empty', !upcoming && liveCount === 0);
    const rail = document.getElementById('today-rail');
    if (rail) rail.hidden = !upcoming;
  }

  function wireStateTabs(labels) {
    const tabs = document.getElementById('state-tabs');
    if (!tabs || tabs.dataset.wired === 'true') return;
    tabs.dataset.wired = 'true';
    tabs.querySelectorAll('button').forEach(button => {
      button.addEventListener('click', () => {
        stateTab = button.dataset.state;
        applyStateTab();
      });
    });
  }

  function renderToday(data) {
    const panel = document.getElementById('today');
    const clears = document.getElementById('today-clears');
    const watching = document.getElementById('today-watching');
    const folded = document.getElementById('today-below-floor');
    if (!panel || !clears || !watching || !folded) return;
    clears.innerHTML = '';
    watching.innerHTML = '';
    folded.innerHTML = '';
    csrfToken = data.csrf || csrfToken;
    const today = (data && data.today) || null;
    if (!today) { panel.hidden = true; return; }
    requireN(today, 'today');
    const labels = today.labels || {};
    const tabs = document.getElementById('state-tabs');
    if (tabs) {
      tabs.querySelectorAll('button').forEach(button => {
        const key = button.dataset.state === 'live' ? 'tab_live' : 'tab_upcoming';
        button.textContent = labels[key] || '';
      });
      wireStateTabs(labels);
    }

    const where = document.getElementById('day-where');
    if (where) where.textContent = today.where_words || '';
    const counts = document.getElementById('day-counts');
    if (counts) counts.textContent = today.count_words || '';
    // THE THREE AGES, EVERY STRING THE SERVER'S. A stale one is marked, and
    // its own words say which threshold it is past; nothing here is red,
    // because the colour law keeps red for a loss.
    const jobs = document.getElementById('day-jobs');
    if (jobs) {
      jobs.innerHTML = '';
      const pulse = (data && data.freshness && data.freshness.entries) || [];
      pulse.forEach(entry => {
        jobs.appendChild(el('span', 'day-job' + (entry.stale ? ' day-job-stale' : ''),
                            entry.words || ''));
      });
    }
    // SAID ONCE FOR THE SLATE. This sentence was appended to every row --
    // thirty times on the football slate of 2026-09-07 -- which is how a page
    // teaches a reader that its rows are not worth reading.
    const note = document.getElementById('day-note');
    if (note) {
      note.textContent = today.no_price_words || '';
      note.hidden = !today.no_price_words;
    }
    const fee = document.getElementById('today-fee');
    if (fee) fee.textContent = today.fee_line || '';
    const taken = document.getElementById('today-taken');
    if (taken) taken.textContent = today.taken_line || '';

    const heading = document.getElementById('today-clears-heading');
    if (heading) heading.textContent = today.clears_heading || '';
    const watchHeading = document.getElementById('today-watching-heading');
    if (watchHeading) watchHeading.textContent = today.watching_heading || '';
    const groupChip = (id, value) => {
      const host = document.getElementById(id);
      if (!host) return;
      host.textContent = value || '';
      host.hidden = !value;
    };
    groupChip('today-clears-chip', today.clears_chip);
    groupChip('today-watching-chip', today.watching_chip);

    // THE MARKET CHIPS FILTER THE GROUPS, not only the slate beneath them.
    // They are declared a filter row on Upcoming; while they filtered the
    // grid alone, opening a market with no picks left the previous market's
    // cards standing in the groups.
    const wanted = state.market || '';
    const keep = list => (list || []).filter(
      e => !wanted || (e.market || '') === wanted);

    renderCombos(today.combos, labels);

    // CONTENT ARRIVES THROUGH THE MOTION BLOCK (2026-09-08). `arrive` was
    // called on the old grid's host; with the grid gone its only caller went
    // with it, and a market switch re-filled the groups with no fade at all.
    // The panel is the container the cards now arrive in.
    arrive(panel);

    keep(today.clears).forEach(e => clears.appendChild(todayCard(e, labels)));
    keep(today.watching).forEach(e => watching.appendChild(todayCard(e, labels)));
    keep(today.below_floor).forEach(e => folded.appendChild(todayCard(e, labels)));

    // LIVE (S3). The cards whose games are being played, taken first, with
    // the score where the start time was. Which cards are here is the
    // poller's answer, not the tab's.
    const liveHost = document.getElementById('today-live');
    const liveHeadingRow = document.getElementById('live-heading-row');
    const liveHeading = document.getElementById('live-heading');
    const liveEmpty = document.getElementById('live-empty');
    if (liveHost) {
      liveHost.innerHTML = '';
      keep(today.live).forEach(e => liveHost.appendChild(todayCard(e, labels)));
      if (liveHeading) liveHeading.textContent = today.live_heading || '';
      if (liveEmpty) {
        const words = document.getElementById('live-empty-words');
        const at = document.getElementById('live-empty-time');
        if (words) words.textContent = today.live_empty_words || '';
        // The instant in the reader's own clock, beside the server's words:
        // two elements, so nothing is glued together.
        if (at) {
          at.textContent = today.live_first_kickoff_utc
            ? localDayTime(today.live_first_kickoff_utc) : '';
        }
      }
    }
    applyStateTab();

    const fold = document.getElementById('today-fold');
    if (fold) {
      fold.textContent = today.below_floor_words || '';
      fold.hidden = !today.below_floor_words;
      fold.setAttribute('aria-expanded', 'false');
      folded.hidden = true;
      fold.onclick = () => {
        folded.hidden = !folded.hidden;
        fold.setAttribute('aria-expanded', folded.hidden ? 'false' : 'true');
      };
    }

    const rail = document.getElementById('today-rail');
    const takenHeading = document.getElementById('taken-heading');
    const entries = document.getElementById('taken-entries');
    if (rail && takenHeading && entries) {
      const list = today.taken_today || { entries: [] };
      takenHeading.textContent = list.heading || '';
      entries.innerHTML = '';
      (list.entries || []).forEach(item => {
        const row = el('div', 'taken-row');
        row.appendChild(el('span', 'taken-what', item.words));
        if (item.taken_utc) {
          row.appendChild(el('time', 'taken-when', localTime(item.taken_utc)));
        }
        entries.appendChild(row);
      });
    }
    panel.hidden = false;
  }

  // WHAT IS WORTH TAKING (R4, 2026-09-07). Placed, never composed: every
  // sentence is written by `language.recommendation_line` and scanned for
  // advice words on the gate. An empty list gets the server's own sentence
  // rather than a hidden section, because "nothing cleared the fee today" is
  // the answer on most days and a blank space is not.
  function renderRecommendations(data) {
    const panel = document.getElementById('week-recommendations');
    const host = document.getElementById('recommendations-list');
    const empty = document.getElementById('recommendations-empty');
    const count = document.getElementById('recommendations-n');
    if (!panel || !host) return;
    host.innerHTML = '';
    const block = (data && data.recommendations) || null;
    if (!block) { panel.hidden = true; return; }
    requireN(block, 'the recommendation list');
    (block.lines || []).forEach(line => {
      requireN(line, 'a recommendation');
      // ONE SENTENCE PER RECOMMENDATION. The size already carries its own
      // reason and its own count -- "0 of 100 settled in this market" -- so a
      // second line saying the same thing printed the same words twelve times
      // down the page. Visible the first time this was rendered.
      const row = el('div', 'gate-row');
      row.appendChild(el('div', 'gate-name', line.words));
      host.appendChild(row);
    });
    if (empty) {
      empty.textContent = (block.lines || []).length ? '' : (block.empty_words || '');
      empty.hidden = !empty.textContent;
    }
    if (count) count.textContent = String(block.n);
    panel.hidden = false;
  }

  // AT THE VENUE'S LINE (E4, 2026-09-06). A second record with its own gate:
  // what the model's frozen distribution says about the venue's own number,
  // beside what the venue's price says about it. PLACED, NOT COMPOSED -- every
  // sentence here is written by `language.at_the_line_*` and scanned for
  // advice words before it ships.
  function renderAtTheLine(sc) {
    const panel = document.getElementById('at-the-line');
    const host = document.getElementById('at-the-line-list');
    const cover = document.getElementById('at-the-line-coverage');
    const venue = document.getElementById('at-the-line-venue');
    const note = document.getElementById('at-the-line-note');
    if (!panel || !host || !cover) return;
    host.innerHTML = '';
    cover.innerHTML = '';
    const atl = (sc && sc.at_the_line) || null;
    if (!atl) { panel.hidden = true; return; }
    if (venue) venue.textContent = atl.venue;
    if (note) note.textContent = atl.note || '';
    (atl.categories || []).forEach(c => {
      requireN(c, 'at-the-line curve "' + c.category + '"');
      const row = el('div', 'gate-row');
      row.appendChild(el('div', 'gate-name', c.category_label));
      row.appendChild(el('div', 'gate-why', c.gate_line));
      if (c.outlook && c.outlook.message) {
        row.appendChild(el('div', 'gate-why', c.outlook.message));
      }
      host.appendChild(row);
    });
    // THE HYPOTHETICAL LEDGER (ruling D1, 2026-09-06). Placed, not composed:
    // the server writes the sentence, and it leads with the word the ruling
    // requires. The fee's provenance goes directly under it, because a
    // fee-adjusted figure whose fee is unverified must say so where it is read.
    (atl.paper || []).forEach(row => {
      requireN(row, 'hypothetical unit ledger');
      const line = el('div', 'gate-row');
      line.appendChild(el('div', 'gate-name', row.words));
      // THE FEE'S PROVENANCE ONLY WHERE THERE IS A FEE-ADJUSTED FIGURE. Under a
      // row that is still counting it repeated a paragraph about an unverified
      // formula three times and said nothing about the record.
      if (row.renderable) line.appendChild(el('div', 'gate-why', row.fee_words));
      host.appendChild(line);
    });
    (atl.coverage || []).forEach(row => {
      cover.appendChild(el('div', 'footnote', row.words));
    });
    panel.hidden = (atl.categories || []).length === 0;
  }

  // WHICH TABLE THIS IS (UI audit finding 6). The market's label and the
  // forecaster's label are the server's own words, placed here.
  function forecasterLabel(f) {
    const known = ((state.scorecard || {}).forecasters || []).find(x => x.forecaster === f);
    return known ? known.label : f;
  }
  function tierTableFor(t) {
    const market = t.market || t.prop_type || t.market_type;
    if (!market) return '';
    return marketLabel(market) + ', ' + forecasterLabel(t.predictor || 'statistical') + ' · ';
  }

  // THE SELECT AND THE PICKER FETCH THE TABLE THEY NAME (UI audit finding 6,
  // 2026-09-05). The select was filled and never wired; the picker set a
  // variable nothing read. Both now ask `/api/tier-table` for the market and
  // forecaster chosen, through the same bucket arithmetic the cards use.
  async function refreshTierTable() {
    const sel = document.getElementById('tier-market');
    const market = sel ? sel.value : '';
    if (!market) return;
    const seq = sportSeq;
    const t = await fetchJSON(withSport('/api/tier-table',
                                        { market: market, forecaster: forecasterChoice }));
    if (stale(seq)) return;
    renderTierTable(t);
  }

  function renderTierTable(t) {
    if (!t) return;
    document.getElementById('tier-caption').textContent =
      DASH + ' ' + tierTableFor(t) + int(t.n) + ' settled, by how sure the model said it was';
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
          (() => {
            const cell = el('div', 'verdict-cell');
            cell.appendChild(
              el('div', r.proven ? 'verdict-words' : 'absent', r.verdict));
            cell.appendChild(gateLine(r.progress));
            return cell;
          })()
        ];
      }));

    // CLOSEST TO A VERDICT, at the top of the tab. Which gate is nearest and
    // roughly how many slates that is -- the sentence is the server's, pace
    // labelled an estimate, and "pace unknown" below a week of history.
    const closest = document.getElementById('closest-verdict');
    if (closest) {
      const c = t.closest || {};
      closest.innerHTML = '';
      if (c.line) {
        closest.appendChild(el('div', 'lead', c.line));
        if (c.note) closest.appendChild(el('div', 'sub', c.note));
      }
      closest.hidden = !c.line;
    }
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

  // THE BREAKPOINT MACHINERY IS GONE (cards UI, 2026-09-04).
  //
  // `DESK_MIN_WIDTH`, `DESK_QUERY` and `isDesk` decided which of TWO layouts
  // to build, and a long comment here explained how the JS and the CSS came to
  // disagree about it -- the renderer building tiles while the media query
  // withheld every tile rule, so the slate rendered as unstyled boxes and the
  // rail looked empty. That whole class of failure is deleted with the second
  // layout: there is one layout now, it reflows, and no code anywhere asks how
  // wide the window is in order to decide what to build.

  // A tile. Every string on it was written by the server: the matchup, the
  // short pick line, the label under the percentage. The renderer places
  // them and computes no words of its own (ruling, 2026-08-31).
  // --- THE CARDS UI (2026-09-04) -------------------------------------------
  //
  // ONE LAYOUT FOR EVERY WIDTH. What stood here was two: a desk (a scrolling
  // frame of tiles beside a fixed rail) above 1280px, and a separate list of
  // compact rows below it. Two layouts describing one slate is two sets of
  // bugs, two sets of tests, and two chances for a card to say something the
  // other one does not. They are deleted -- markup, CSS and tests -- with no
  // allowlist entries, the way the calls feature was withdrawn.
  //
  // NOTHING HERE BUILDS A SENTENCE. `row_title`, `phrase`, `chance_clause`,
  // `bucket_line`, `rate_line`, `what_it_knew` and every `why` sentence arrive
  // written from `language.py`. That is what stopped the renderer inventing a
  // verb and getting the side backwards twice.

  //: How many cards the grid shows before "show all". Six, from the brief.
  // THE HERO IS GONE (THREE_STATES S1, 2026-09-08) and so is the pool it
  // stepped through: `heroPool` and `HERO_STEPS` stood here with no caller
  // until NIGHT_AUDIT item 6 measured that and removed them.
  function localTime(iso) {
    try {
      return new Date(iso).toLocaleTimeString([], {
        hour: 'numeric', minute: '2-digit'
      });
    } catch (e) { return ''; }
  }

  // What follows the pick on the line: kick-off for a game, the fixture for a
  // prop, because on a prop the subject is the headline and the fixture is the
  // detail.
  // `cardTail` STOOD HERE, for the old grid card's time slot. Removed
  // with that card on 2026-09-08.

  function tierChip(tier) {
    if (!tier || !tier.tier) return el('span', 'tier tier-none', '');
    // THE CHIP SAYS WHETHER IT IS A RECORD OR A CLAIM (2026-09-04), and the
    // server writes that. `chip_label` is "STRONG" once the band has earned a
    // verdict and "STRONG · unproven" until then.
    //
    // IT USED TO BE THE TIER WORD ALONE, with the whole story in `title` --
    // which is a hover tooltip, so on a phone it did not exist. Measured
    // across four live slates: 362 of 379 chips named a band with nothing
    // behind it, and only the hero ever said so out loud.
    //
    // `|| tier.tier` IS NOT A FALLBACK THAT COMPOSES ANYTHING. It renders the
    // bare band an older payload would carry, and adds no words of its own.
    const chip = el('span', 'tier ' + tier.tier.toLowerCase(),
                    tier.chip_label || tier.tier);
    if (!tier.proven) chip.classList.add('tier-unproven');
    chip.title = tier.message || '';
    return chip;
  }

  // ONE NUMBER, AND THE WORD FOR WHAT IT IS A NUMBER OF (R2). The percentage
  // and "chance" beneath it, and nothing else numeric on a collapsed card --
  // the market's figure is inside, one tap away, because a card showing two
  // percentages makes a reader work out which one is the claim.
  // `chanceBlock`, `marketHint` and `pickCard` STOOD HERE: the old Picks
  // card, with the raw probability as its largest element and a tier chip
  // on every one. CARD_FACE replaced that design and THREE_STATES took the
  // hero off the top of it, but the grid itself was never named for removal
  // and survived both -- so the page rendered two card designs at once,
  // which is what the operator saw on 2026-09-08. Removed by his ruling.

  // --- FOLLOWING A SLATE THAT IS ON (L2) ------------------------------------
  //
  // Sixty seconds, and ONLY while something is live. `any_live` comes from the
  // server and is the whole of the stop condition: a slate that finished hours
  // ago is polled zero times. The compact payload is about 3KB against 190KB
  // for the full slate, which is why this is a second endpoint rather than a
  // re-fetch.
  //
  // CARRIED ACROSS FROM THE TILES, not rebuilt from scratch, and the rule it
  // exists to keep is unchanged: A SCORE ARRIVING DOES NOT MOVE THE SLATE. The
  // grid is never rebuilt and never re-sorted on a tick -- re-sorting while
  // games are being played shuffles the screen under a reader part way down
  // it, and by confidence the finished games would climb over the ones still
  // on.
  const LIVE_POLL_MS = 60000;
  let livePollTimer = null;

  // `slateCards` STOOD HERE, indexing the old grid's cards so a tick could
  // patch one of them. The tick re-renders now; nothing indexes cards.

  function stopLivePolling() {
    if (livePollTimer) { clearInterval(livePollTimer); livePollTimer = null; }
  }

  function startLivePolling(data) {
    stopLivePolling();
    if (!data || !(data.glance || {}).state || data.glance.state === 'complete') return;
    // NO SLATE, NO POLL (UI audit finding 25, 2026-09-06). An empty payload
    // has no week; the poll asked `/api/live?week=null` every minute and was
    // refused with a 422 on every NBA visit. The race fix exposed it: before,
    // the NBA tab was polling for whichever sport's cards had leaked onto it.
    if (data.week === null || data.week === undefined || !(data.cards || []).length) return;
    const seq = weekSeq;
    const tick = async () => {
      if (state.view !== 'week') { stopLivePolling(); return; }
      let live;
      try {
        live = await fetchJSON(withSport('/api/live?season=' + data.season +
                                         '&week=' + data.week));
      } catch (err) {
        // A POLL THAT FAILS IS NOT A REASON TO STOP FOLLOWING. The next tick
        // tries again; what must not happen is the scores silently freezing
        // with no sign that they have.
        console.error('live poll failed:', err);
        return;
      }
      if (seq !== weekSeq) { stopLivePolling(); return; }
      applyLive(live);
      if (!live.any_live) stopLivePolling();
    };
    tick();
    livePollTimer = setInterval(tick, LIVE_POLL_MS);
  }

  // THE TICK PATCHES THE CARD IN PLACE (2026-09-08).
  //
  // `applyLive` used to reach for `.card[data-id=...]` -- the OLD grid card's
  // class -- and `applyCardState` moved that card's internals between states.
  // Both went with the grid, and for an hour this function called
  // `renderWeek()` instead. THAT IS THE ONE THING THE GUARD FORBIDS:
  // `audit.live_update_faults` refuses a re-render or a re-sort on a tick,
  // because a reader part way down a slate must not have the thing they are
  // looking at move. The plantings caught it; this is the repair.
  //
  // EVERY STRING IS THE SERVER'S. The compact live payload carries
  // `score_line`, `clock_line` and `verdict`, composed by the same humaniser
  // the full payload uses, so nothing is written in the browser.
  //
  // IT PATCHES SCORES, NOT STATES. A game that has just gone live belongs in
  // a different group, and which group a card sits in is decided on the
  // server from `games.status`. The tick keeps the score current on cards
  // already showing; the next render moves them.
  function applyLive(live) {
    (live.picks || []).forEach(pick => {
      const node = document.querySelector(
        '.face[data-id="' + pick.prediction_id + '"]');
      if (!node) return;
      const put = (cls, words) => {
        const el = node.querySelector(cls);
        if (el && words) el.textContent = words;
      };
      put('.face-score', pick.score_line);
      put('.face-period', pick.clock_line);
    });
  }

  // RESTORED 2026-09-08, verbatim. Removing `applyCardState` cut from
  // its opening brace to the next top-level boundary and took six
  // neighbours with it -- `arrive`, `renderMarketTabs`,
  // `renderYesterday`, `placeGreeting`, `probBlock` and `clamp01`.
  // The page threw `placeGreeting is not defined` on boot, which is
  // how it was found. Only `applyCardState` was meant to go.
  function arrive(node) {
    if (!node) return;
    node.classList.add('arriving');
    void node.offsetHeight;
    requestAnimationFrame(() => node.classList.remove('arriving'));
  }
  function renderMarketTabs(data, active) {
    const host = document.getElementById('week-market-tabs');
    if (!host) return;
    host.innerHTML = '';
    const tabs = data.market_tabs || [];
    if (!tabs.length) { host.hidden = true; return; }
    host.hidden = false;
    tabs.forEach(t => {
      const b = el('button', 'market-tab', t.label);
      b.type = 'button';
      b.dataset.market = t.market || '';
      const on = (t.market || '') === (active || '');
      b.setAttribute('aria-pressed', String(on));
      if (on) b.classList.add('on');
      // ZERO-COUNT TABS STAY VISIBLE. "No strikeout questions tonight" is a
      // fact about the slate, and a tab that disappears hides it.
      b.appendChild(el('span', 'market-tab-n', String(t.n)));
      b.addEventListener('click', () => {
        state.market = t.market || '';
        renderWeek().catch(showError);
      });
      host.appendChild(b);
    });
  }

  // --- the yesterday strip --------------------------------------------------

  function renderYesterday(data) {
    const host = document.getElementById('week-yesterday');
    if (!host) return;
    host.innerHTML = '';
    const y = data.yesterday;
    if (!y) { host.hidden = true; return; }
    host.hidden = false;

    const left = el('div', 'yesterday-line');
    left.appendChild(el('span', 'yesterday-label', y.label));
    // GREEN ON THE RIGHT COUNT ONLY (the colour law). The wrong count is
    // drawn in the ordinary ink: red is reserved for a pick that lost, and a
    // tally is not a pick.
    left.appendChild(el('b', 'win', String(y.right)));
    left.appendChild(el('span', '', ' right, '));
    left.appendChild(el('b', '', String(y.wrong)));
    left.appendChild(el('span', '', ' wrong'));
    host.appendChild(left);

    if (y.season) host.appendChild(el('div', 'yesterday-season', y.season));
    if (y.next_verdict) {
      host.appendChild(el('div', 'yesterday-next', y.next_verdict));
    }
  }

  // THE GREETING STAYS WHERE THE MARKUP PUT IT. It used to be MOVED into the
  // desk rail's third panel and back again below the breakpoint -- one set of
  // nodes living in two places depending on viewport width. The rail is gone
  // and so is the move: there is one greeting, in one place, at every width.
  function placeGreeting() {
    const greeting = document.getElementById('greeting');
    const home = document.getElementById('greeting-home');
    if (!greeting || !home) return;
    if (greeting.parentElement !== home) home.appendChild(greeting);
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

  // A SECOND `tierChip` STOOD HERE AND HAD BEEN DEAD FOR SOME TIME. It took a
  // CARD where the surviving one takes a TIER, and it sat earlier in the file
  // than its namesake -- so JavaScript's last-declaration-wins rule meant it
  // never ran, and its `null` return for a card with no tier never reached
  // anything. Deleting the desk moved the survivor ABOVE it, at which point
  // the dead one started winning and every tier chip on the slate became
  // `appendChild(null)`.
  //
  // Found by patching `Node.prototype.appendChild` to throw on a non-node and
  // reading the stack, which named the line in four seconds after twenty
  // minutes of reading. Worth remembering: a shadowed duplicate is invisible
  // until something reorders the file.

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


  function buildCardBody(body, c) {
    body.innerHTML = '';

    // MODEL, MARKET AND GAP AS TEXT (GRIDIRON_16 R3). A dot-and-span graphic
    // stood here until 2026-09-02: it showed these three numbers and made the
    // reader estimate two of them off a 100-pixel track, which is a worse way
    // to read a percentage than reading the percentage. The sentence is
    // written by `language.rail_numbers_line`; this places it.
    body.appendChild(el('p', 'card-numbers', c.rail_line || ''));

    // THE RATE, DIRECTLY UNDER THE NUMBER IT EXPLAINS (C3, 2026-09-03).
    // "The model expects about 3.9 receptions; clearing 3.5 is about 56%."
    // A count market answers in two steps and the reader is entitled to both:
    // the percentage alone says nothing about whether the model thinks he
    // catches four passes or nine. Present only on a count market -- a
    // continuous market has no rate and the server sends an empty string.
    // Composed by `language.rate_line`; this places it.
    if (c.rate_line) {
      body.appendChild(el('p', 'card-rate', c.rate_line));
    }

    // AT THE VENUE'S LINE (E4, 2026-09-06), one tap into the card. The model's
    // own distribution read at the number the venue published after this
    // forecast was written and frozen, beside what the venue's price implies
    // for the same question. The server writes the sentence; this places it,
    // and the gate line beneath it says how many have settled.
    // WHY THIS ONE IS IN FRONT (THE_SHORTLIST S2, 2026-09-07). The three
    // inputs in the reader's own terms, including whether the disagreement
    // with the line counted toward the order or is only recorded. Composed by
    // `language.shortlist_rank_line`; this places it.
    if (c.rank_line) {
      body.appendChild(el('p', 'card-rank', c.rank_line));
    }

    // THE SECOND FORECASTER (THE_PRICED P1, 2026-09-07), one tap into the
    // card and clearly labelled as the one that read the price. The headline
    // percentage above stays the blind forecast's.
    if (c.priced_line) {
      body.appendChild(el('p', 'card-priced', c.priced_line));
    }

    if (c.at_the_line && c.at_the_line.words) {
      body.appendChild(el('p', 'card-at-the-line', c.at_the_line.words));
      body.appendChild(el('p', 'footnote', c.at_the_line.gate_line));
    }

    const line = el('div', 'card-stats');
    line.appendChild(el('span', 'card-bucket', c.bucket_line || ''));
    body.appendChild(line);

    // THE RAW CLAIM, ONE TAP AWAY. Present only where a correction actually
    // moved the number, so a card in a raw category is byte-identical to what
    // it was before corrections existed. The sentence is written by the
    // server; this places it.
    if (c.earned_line) {
      body.appendChild(el('p', 'card-earned', c.earned_line));
    }

    // THE PLAIN WHY (K3). The contribution bars and the decomposition sentence
    // that used to sit here have moved to the Factors page, which is where
    // somebody auditing the model goes looking for them. What a reader wants on
    // a pick is which few things drove it and how hard, in words.
    //
    // Every sentence is written by `language.why_block` from the SAME
    // contributions the decomposition uses, so the prose and the arithmetic
    // cannot disagree about direction or order.
    const why = el('div', 'card-why');
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

    const more = el('a', 'card-more',
      ((w && w.more_label) || 'How the model works') + ' \u2192');
    more.href = (w && w.more_href) || '#/factors';
    body.appendChild(more);

    // PLACED, NOT COMPOSED (S3). This used to build the sentence here --
    // `tier.tier + ' tier ' + message.replace(/^tier /, '')` -- which is the
    // renderer writing prose, and it broke the moment the server's message
    // started naming its own band: it would have read "STRONG tier STRONG -
    // 8 settled". The server writes the whole sentence now.
    if (c.tier && c.tier.message) {
      body.appendChild(el('div', 'card-tierline', c.tier.message));
    }
    // THE MODEL'S WORST BAND, beside this pick's band, so a reader sees what
    // the record says at its weakest and not only what this chip says.
    if (c.worst_band) {
      body.appendChild(el('div', 'footnote', c.worst_band));
    }
  }

  // THE TIER FILTER (R2). A fourth segmented control beside sort and market.
  //
  // REMEMBERED IN MEMORY ONLY, per sport. The choice should survive switching
  // to Record and back, and should NOT survive closing the app: a filter a
  // reader forgot they set is a slate that looks emptier than it is, and the
  // one thing worse than a hidden filter is a hidden filter that outlives the
  // session. No storage API is touched.
  //
  // THIS DECLARATION WAS DELETED BY ACCIDENT on 2026-09-02 and restored the
  // same day. `resolvedRow` was removed by cutting from its `function` line
  // to the next one, and this const sat between the two -- so the cut took it
  // as well. Nothing failed at import: `tierChoice` is only read once the
  // slate renders, and the ReferenceError surfaced as a blank Picks page with
  // fourteen browser tests timing out on a selector.
  const tierChoice = new Map();

  //: WHICH TIER PICKS OPENS ON (ruling R2, 2026-09-02). The server declares
  //: it; this places it. A reader's first question is what the model is most
  //: sure of, and a slate sorted by disagreement puts fifty LEAN picks in
  //: front of that.
  //:
  //: REMEMBERED FOR THE SESSION, per sport, in memory only -- the same rule
  //: the choice already followed. A filter a reader forgot they set is a
  //: slate that looks emptier than it is, and one that outlives the session
  //: is worse.
  let defaultTier = 'STRONG';

  function currentTier() {
    const chosen = tierChoice.get(state.sport);
    return chosen === undefined ? defaultTier : chosen;
  }

  //: THE DEFAULT IS A CONVENIENCE, NOT A CLAIM. On a slate with no STRONG
  //: picks on it, opening on STRONG would show an empty list under a filter
  //: the reader never chose -- which reads as "nothing was forecast tonight"
  //: and is the opposite of true. So the default applies only where the band
  //: actually exists; a reader's OWN choice is honoured either way, empty
  //: result included, because that is a question they asked.
  function effectiveTier(cards) {
    const chosen = tierChoice.get(state.sport);
    if (chosen !== undefined) return chosen;
    return cards.some(c => tierOf(c) === defaultTier) ? defaultTier : '';
  }

  function setTier(tier) {
    tierChoice.set(state.sport, tier || '');
    renderWeek();
  }

  function tierOf(card) {
    // NO CASE CHANGE. The server sends the tier already in the form it is
    // displayed in, and re-casing a stored value in the browser is the exact
    // move the prose tripwire watches for -- it is how
    // `String(s.subject).toUpperCase()` came to shout a raw identifier at a
    // reader. Compared as sent, shown as sent.
    return (card.tier || {}).tier || '';
  }
  // WHICH FORECASTER AND WHICH PASS, PER SPORT. The View menu that set these
  // was removed on 2026-09-08 with the rest of the old Picks page; the choice
  // itself is still read -- the day strip says whose questions it counts --
  // and the map went with the menu by accident. Restored, because a page that
  // cannot say which forecaster it is showing is the defect that strip was
  // built to fix.
  const viewChoice = new Map();

  function currentView() {
    return viewChoice.get(state.sport) || { forecaster: null, early: false };
  }

  function setView(patch) {
    viewChoice.set(state.sport, Object.assign({}, currentView(), patch));
  }

  // WHICH TOGGLE WAS CHOSEN, so that after the slate re-renders -- and the
  // toggles with it -- focus lands on the new copy of the pressed button
  // rather than on the body (UI audit finding 4).
  let viewFocus = null;
  function paintClock(glance, slateTitle) {
    const host = document.getElementById('week-clock');
    const line = document.getElementById('week-clock-line');
    // THE SLATE'S NAME IS THE HEADING NOW, so the clock no longer repeats it.
    // Adding the H1 put "Week 18, 2025" twice within three lines -- the same
    // words in two places, which is the duplication this project keeps having
    // to remove (the market column, the pick sentence, the tier label).
    if (!host || !line) return;
    if (!glance) { host.hidden = true; return; }

    if (glance.state_line) {
      // In progress or complete: a fact that does not change until a game
      // ends, so it is written once by the server and placed here.
      line.textContent = glance.state_line;
      host.hidden = false;
      return;
    }
    if (!glance.first_kickoff_utc) { host.hidden = true; return; }

    // THE WORD IS THE SERVER'S AND THE TIME IS THE READER'S CLOCK: two
    // elements, so nothing is glued together and nothing counts down. The
    // date travels with the time because a slate's first game can be days
    // away, and a bare "1:05 PM" would read as today.
    line.textContent = '';
    line.appendChild(el('span', 'clock-word', glance.state_word || ''));
    // A SEPARATOR, not a sentence. Two elements with a margin between them
    // read correctly on screen and run together in the page's text content,
    // which is what every rendered-text scan reads.
    line.appendChild(document.createTextNode(' '));
    line.appendChild(el('time', 'clock-time',
                        localDayTime(glance.first_kickoff_utc)));
    host.hidden = false;
  }

  // A start instant as the reader's own calendar and clock show it. The one
  // thing this file works out for itself, for the one reason it is allowed
  // to: the browser is the only party that knows the timezone.
  function localDayTime(iso) {
    try {
      return new Date(iso).toLocaleString([], {
        weekday: 'short', month: 'short', day: 'numeric',
        hour: 'numeric', minute: '2-digit',
      });
    } catch (e) { return ''; }
  }

  async function renderWeek() {
    const host = document.getElementById('week-cards');
    // THE SKELETON WENT WITH THE GRID (2026-09-08). It drew hairline card
    // shapes in the grid's geometry so the layout would not jump when the
    // data landed; with no grid there are no shapes to hold a place for, and
    // the sentences this container now carries arrive with the payload.

    const picker = document.getElementById('week-picker');
    const chosen = picker.value ? JSON.parse(picker.value) : {};
    let qs = chosen.season ? ('?season=' + chosen.season + '&week=' + chosen.week) : '';
    // WHOSE PICKS. Absent on the first load, so the server applies its own
    // default rather than the browser having a second opinion about which
    // forecaster leads.
    const view = currentView();
    if (view.forecaster) {
      qs += (qs ? '&' : '?') + 'forecaster=' + encodeURIComponent(view.forecaster);
    }
    //: WHICH FORECAST (A3). Off by default: Picks shows the standing row, the
    //: one the record is graded on. Session-only, like the tier and the
    //: forecaster -- a reader who left the early view open yesterday should
    //: not find yesterday's forecasts waiting for them today.
    if (view.early) qs += (qs ? '&' : '?') + 'early_view=true';
    const seq = ++weekSeq;
    const data = await fetchJSON(withSport('/api/week' + qs));
    if (seq !== weekSeq) return;
    clearError();
    if (data.default_tier) defaultTier = data.default_tier;
    // THE TAB IS THE FILTER (UI audit finding 24, 2026-09-05). The cards were
    // filtered on the hidden Market select inside "This week", and the tab
    // click set only the pressed state -- so every tab showed the whole slate,
    // the zero-count tab included, and the counts line never changed. One
    // source of truth: `state.market`, set by the tab or by the select, and
    // the select mirrors it. A market the new sport does not ask falls back
    // to All rather than filtering the slate to nothing.
    const select = document.getElementById('week-market');
    if (state.market && !(data.market_tabs || []).some(t => (t.market || '') === state.market)) {
      state.market = '';
    }
    const market = state.market || '';
    if (select && select.value !== market) select.value = market;

    // PLACED, NOT COMPOSED. The server names the slate in words; this used to
    // glue the season to the raw key and print "Season 2026, week 20260905".
    document.getElementById('week-title').textContent = data.slate_title || '';
    // The standing note, in the mockup's words. Agreeing with the market is
    // not a finding, which is why disagreement is the default order.
    document.getElementById('week-sort').textContent =
      state.weekSort === 'confidence'
        ? 'Sorted by how sure the model is. ' + data.n + ' forecasts.'
        : 'Agreeing confidently with the market is not a finding.';
    paintClock(data.glance, data.slate_title);

    startLivePolling(data);

    host.innerHTML = '';
    let cards = market ? data.cards.filter(c => c.market === market) : data.cards;
    // Indexed BEFORE the filters narrow the view, so the rail can still
    // describe a pick the reader selected under a different filter.

    // THE TIER FILTER NARROWS AFTER THE MARKET ONE, and the count line below
    // reports both the part and the whole -- four picks looks like a thin
    // slate rather than a narrow filter unless the denominator is beside it.
    const wholeSlate = cards.length;
    if (viewFocus) {
      viewFocus = null;
    }
    const tier = effectiveTier(cards);

    if (tier) cards = cards.filter(c => tierOf(c) === tier);
    if (state.weekSort === 'confidence') {
      cards = cards.slice().sort((a, b) => (shownProb(b) || 0) - (shownProb(a) || 0));
    }

    placeGreeting();
    // THE TABS AND THE STRIP, both fed from the same payload the cards are.
    // The tabs come from the sport's DECLARED market list (R4) and the strip
    // reports one sport's yesterday, never a total across sports.
    // THE HEADING. Written by the server; placed here.
    const headline = document.getElementById('week-headline');
    if (headline) headline.textContent = data.headline || '';
    renderMarketTabs(data, state.market);
    renderYesterday(data);

    // A resolved forecast is not a pick. Split rather than filtered, so the
    // slate can show both without a reader mistaking last night for tonight.
    // A RESOLVED FORECAST IS NOT A PICK -- except while its own slate is
    // still being played. Splitting them unconditionally meant a game ending
    // made its tile VANISH from the grid and reappear in a list below, which
    // is precisely the shuffle L2 forbids: the reader is part way down a
    // slate and the thing they were looking at moves. While the slate is in
    // progress every pick keeps its place and the finished ones take a
    // verdict chip; once the slate is complete the old split returns, so
    // last night and tonight are still never mixed.
    const slateRunning = (data.glance || {}).state === 'live';
    const settled = c => c.resolved_utc !== null || c.voided;
    const open = slateRunning ? cards : cards.filter(c => !settled(c));
    // COUNTED, NOT LISTED (GRIDIRON_16 R4). Settled picks live in Results.
    // They are still counted here for one reason: a slate that has finished
    // must say so, rather than rendering nothing at all.
    const settledCount = slateRunning ? 0 : cards.filter(settled).length;

    // THE CONTROLS LINE. A thin slate has to explain itself: eight picks on a
    // fourteen-game card looks like a failure until the floor is named.
    const counts = document.getElementById('week-counts');
    if (counts) {
      // ONE WRITER FOR THIS ELEMENT. A second one was added here for the tier
      // filter and the two fought over the same node: the page threw
      // "Identifier 'counts' has already been declared" and never became
      // ready -- the loudest possible version of a duplicate, and by far the
      // kindest, because a silent second writer would have won a race
      // intermittently.
      //
      // LOOKED UP, NOT COMPOSED: the server wrote a line for every
      // combination of the two filters, so the count and its denominator are
      // its words rather than a sentence glued together here.
      const lines = (data.glance || {}).count_lines || {};
      const bits = [data.slate_word === 'day' ? 'tonight' : 'this week',
                    lines[(market || '') + '|' + tier] ||
                    lines['|' + tier] || ''];
      // `tier` is what was APPLIED, not what was defaulted to, so a slate with
      // no STRONG on it reads "45 picks" rather than naming a band nobody saw.
      if (data.below_floor) {
        bits.push(data.below_floor + ' below the ' +
                  Math.round((data.floor || 0.7) * 100) + '% floor');
      }
      // WHERE THE REST WENT (UI audit finding 9). Once a slate is not live
      // its settled picks leave the grid; the line says how many did.
      if (!slateRunning) {
        const settledLine = ((data.glance || {}).settled_lines || {})[(market || '') + '|' + tier];
        if (settledLine) bits.push(settledLine);
      }
      counts.textContent = bits.filter(Boolean).join(' · ');
    }

    // THE CAVEAT UNDER THE FILTER. Opening on STRONG puts the most confident
    // claims first AND the tier with the fewest settled rows behind them;
    // saying so is the point. The server writes the sentence and stops
    // sending it once the band earns its verdict.
    const caveat = document.getElementById('tier-caveat');
    if (caveat) {
      const show = data.tier_caveat && tier === (data.default_tier || '');
      caveat.textContent = show ? data.tier_caveat : '';
      caveat.hidden = !show;
    }

    // TODAY IS DRAWN BEFORE THE EMPTY BRANCH, not inside the branch that has
    // cards. It used to be called only where cards existed, so switching to a
    // sport with no forecasts left the LAST sport's cards standing in the
    // groups -- fifteen of them, found by
    // `test_a_sport_with_no_forecasts_shows_nothing_of_the_last_one` on
    // 2026-09-08. That test exists because the same shape of defect left a
    // hero behind in September.
    renderToday(data);

    if (!open.length) {
      // A FINISHED SLATE SAYS SO AND POINTS AT RESULTS.
      // NOTHING OF THE LAST SLATE SURVIVES AN EMPTY ONE (UI audit finding 2,
      // 2026-09-05). This branch returned before it touched the grid
      // heading or the show-all button, so the NBA tab -- no forecasts until
      // October -- opened on a "More picks" heading over nothing and a
      // "show all 7" button that showed nothing. The hero it also left
      // standing was removed with the rest of that page on 2026-09-08.
      //
      // This tested `!open.length && !done.length` while a resolved section
      // still rendered underneath. With that section gone (R4) the same
      // condition left a slate whose games had all finished showing NOTHING
      // AT ALL: no picks, and no sentence either, because `done` was not
      // empty. A blank page is the one answer a reader cannot act on.
      if (settledCount) {
        const finished = el('div', 'empty');
        finished.appendChild(document.createTextNode(
          'Every pick on this slate has been settled. '));
        const link = el('a', '', 'See them in Results →');
        link.href = '#/results';
        finished.appendChild(link);
        host.appendChild(finished);
        return;
      }
      // WHOSE picks are missing, when that is why the list is empty. "No
      // forecasts recorded for this slate yet" is false on a slate that has
      // 23 of them from the other forecaster, and a reader who just changed
      // the selector would read it as a broken page.
      host.appendChild(el('div', 'empty', data.forecaster_message || data.message ||
        (market ? 'No ' + marketLabel(market) + ' forecasts on this slate.'
                : 'No forecasts recorded for this slate yet.')));
      (data.quiet_markets || []).forEach(q =>
        host.appendChild(el('div', 'quiet-market', q)));
      return;
    }

    // THE CARDS ARE THE PAGE, AND THERE IS ONLY ONE SET OF THEM
    // (2026-09-08). The grid that stood here rendered every shortlisted
    // question a second time, in the design CARD_FACE replaced. What it
    // showed that the groups above do not is the NON-shortlisted
    // questions, and those are reachable on Results and in the record;
    // the ruling is that one screen shows one set of cards.
    // A market the slate asked nothing in says so, rather than leaving a gap
    // that reads as a failure to find questions.
    (data.quiet_markets || []).forEach(q =>
      host.appendChild(el('div', 'quiet-market', q)));

    // NO RESOLVED SECTION ON PICKS (GRIDIRON_16 R4). Settled rows live in
    // Results and only there. Picks answers "what does the model say about
    // tonight"; a list of what already happened underneath it answers a
    // different question and made the page longer every day of the season.
  }

  async function loadWeekPicker() {
    const seq = sportSeq;
    const data = await fetchJSON(withSport('/api/weeks'));
    if (stale(seq)) return;
    const picker = document.getElementById('week-picker');
    picker.innerHTML = '';
    data.weeks.forEach(w => {
      const o = el('option', '', w.label);
      o.value = JSON.stringify({ season: w.season, week: w.week });
      picker.appendChild(o);
    });
  }

  async function loadMarkets() {
    const seq = sportSeq;
    const data = await fetchJSON(withSport('/api/markets'));
    if (stale(seq)) return;
    // `game_markets`, not `spread`. s1 renamed this field on the server and
    // the browser was never updated, so `data.spread.concat` threw on every
    // boot — silently, because it happened inside boot's catch. The week
    // picker and the chart's market selector have been EMPTY ever since,
    // and no test looked at them.
    state.markets = (data.game_markets || []).concat(data.props || []);
    state.retired = data.retired || {};
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
        // A retired market is not offered on Picks; it stays on Results,
        // labelled, because its settled rows are still there to read.
        if (id === 'week-market' && state.retired[m]) return;
        const o = el('option', '', marketLabel(m)); o.value = m; sel.appendChild(o);
      });
      // A filter that survives the switch only if the new sport has it.
      sel.value = state.markets.includes(keep) ? keep : '';
    });
  }

  // --- VERSIONS -----------------------------------------------------------
  async function renderVersions() {
    const seq = sportSeq;
    const data = await fetchJSON(withSport('/api/versions'));
    if (stale(seq)) return;
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
            return [categoryLabel(c), int(c.n), num(c.brier),
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
      const seq = sportSeq;
      const data = await fetchJSON(withSport('/api/week'));
      if (stale(seq)) return;
      const card = (data.cards || []).find(c => (c.top_factors || []).length);
      if (!card) { host.hidden = true; return; }

      // THE SERVER'S SENTENCE, placed. It was glued together here out of a
      // dash, a subject and a percentage until 2026-09-07.
      document.getElementById('worked-caption').textContent =
        card.example_caption || '';
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
    const seq = sportSeq;
    const data = await fetchJSON(withSport('/api/factors'));
    if (stale(seq)) return;
    requireN(data, 'factor report');
    document.getElementById('factors-caption').textContent =
      DASH + ' scored over ' + int(data.n) + ' resolved statistical predictions';
    document.getElementById('factors-method').textContent = data.method;
    await renderWorkedExample();

    renderFactorCards(data.factors);

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

  // ONE CARD PER FACTOR (GRIDIRON_13 P5). Every string is the server's: the
  // plain name, the one-line "what it measures" (`language.factor_what`), and
  // the earned pull in words WITH ITS N. The renderer places them and filters.
  let factorCards = [];

  function renderFactorCards(factors) {
    factorCards = factors || [];
    const host = document.getElementById('factors-cards');
    const box = document.getElementById('factors-search');
    if (!host) return;
    if (box && !box.dataset.wired) {
      box.dataset.wired = '1';
      box.addEventListener('input', () => paintFactorCards(box.value));
    }
    paintFactorCards(box ? box.value : '');
  }

  function paintFactorCards(query) {
    const host = document.getElementById('factors-cards');
    const note = document.getElementById('factors-search-note');
    if (!host) return;
    // BY PLAIN NAME, which is the name a reader has. Searching the code would
    // only help somebody who already knows the identifier, and they have the
    // table underneath.
    //
    // A CASE-INSENSITIVE REGEX RATHER THAN `.toLowerCase()`. The renderer
    // scan refuses a case change on a value, because
    // `String(s.subject).toUpperCase()` once shouted a raw identifier at a
    // reader -- and it cannot tell a comparison from a display. Matching with
    // a flag transforms nothing at all, which is both what the rule is
    // protecting and simply the better way to do it.
    const needle = String(query || '').trim();
    const pattern = needle
      ? new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i')
      : null;
    const shown = pattern
      ? factorCards.filter(f => pattern.test(String(f.plain_name || f.factor)))
      : factorCards;
    host.innerHTML = '';
    shown.forEach(f => {
      const card = el('div', 'fcard');
      card.appendChild(el('div', 'fcard-name', f.plain_name || f.factor));
      card.appendChild(el('div', 'fcard-what', f.what || ''));
      // THE N IS IN THE WORDS the server wrote -- "moves the answer a lot ·
      // 18 picks" -- so LAW 4 is satisfied by the sentence, not by a number
      // this renderer decided to append.
      card.appendChild(el('div', 'fcard-pull', f.earned_words || ''));
      if (!f.active) card.appendChild(el('span', 'tag', 'inactive'));
      // THE ONE SANCTIONED CODE, small beneath, excluded from the plain-words
      // scan by position because a reader matching a row against the registry
      // needs the literal.
      card.appendChild(el('div', 'factor-code', f.factor));
      host.appendChild(card);
    });
    if (note) {
      note.textContent = pattern
        ? shown.length + ' of ' + factorCards.length + ' factors match'
        : '';
      note.hidden = !pattern;
    }
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
    // THE CALENDAR'S SELECTION (GRIDIRON_13 P2). One day, or the season.
    if (state.calendarDay) p.set('day', state.calendarDay);
    p.set('limit', '100');
    p.set('offset', String(state.historyOffset));
    return p.toString();
  }

  // PENDING / WIN / LOSS / VOID, in the card language. "open" is not a word
  // anybody says about a forecast that has not happened yet.
  // "receiving_yards / statistical" -> "receiving yards, statistical"
  // THE SERVER'S WORDS, never the key (audit 2026-09-05). Splitting the
  // category on its slashes printed the middle part raw, which on a tiered
  // sport is the tier key -- "fight_night" on every row of the UFC record.
  function categoryLabel(c) {
    if (c && c.category_label) return c.category_label;
    const parts = String((c && c.category) || c).split(' / ');
    const market = marketLabel(parts[0]);
    return parts.length > 1 ? market + ', ' + parts[parts.length - 1] : market;
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

  // THE SEASON AS A SHAPE (GRIDIRON_13 P2).
  //
  // WEEKS ARE ROWS, so a column is a weekday and a season has a readable
  // shape. Every square's words -- the balance, the label, the sentence a
  // reader gets on hover -- are written by the server; this places them and
  // decides nothing about what a day means.
  //
  // A DAY WITH NO RESULT IS A HAIRLINE SQUARE, not a gap: "nothing settled
  // here" and "nothing is known here" look identical as empty space, and
  // only one of them is true.
  async function renderCalendar() {
    const panel = document.getElementById('calendar-panel');
    const grid = document.getElementById('calendar-grid');
    const months = document.getElementById('calendar-months');
    const note = document.getElementById('calendar-note');
    const caption = document.getElementById('calendar-caption');
    if (!panel || !grid) return;

    const seq = sportSeq;
    const data = await fetchJSON(withSport('/api/calendar'));
    if (stale(seq)) return;
    const days = data.days || [];
    grid.innerHTML = '';
    months.innerHTML = '';
    if (!days.length) { panel.hidden = true; return; }
    panel.hidden = false;

    // Pad to the start of the week so the columns line up as weekdays.
    const first = new Date(days[0].day + 'T00:00:00');
    const lead = (first.getDay() + 6) % 7;          // Monday-first
    for (let i = 0; i < lead; i++) {
      grid.appendChild(el('div', 'day empty'));
    }

    const today = new Date().toISOString().slice(0, 10);
    days.forEach(d => {
      const cell = el('button', 'day');
      cell.type = 'button';
      cell.dataset.day = d.day;
      // THE TINT IS THE DAY'S BALANCE and the server computed it. The
      // renderer does not compare won against lost -- a second opinion about
      // which way a day went is exactly what `audit.calendar_faults` exists
      // to stop reaching a reader.
      if (d.settled) {
        cell.classList.add('has-result', d.balance);
        cell.textContent = d.label;
      } else {
        cell.classList.add('empty');
      }
      if (d.day === today) cell.classList.add('today');
      if (d.day === state.calendarDay) cell.classList.add('sel');
      cell.title = d.words || '';
      if (d.void) {
        const dot = el('span', 'voids');
        dot.title = d.void + ' void';
        cell.appendChild(dot);
      }
      if (d.settled) {
        cell.addEventListener('click', () => {
          state.calendarDay = (state.calendarDay === d.day) ? null : d.day;
          state.historyOffset = 0;
          renderResults().catch(showError);
        });
      }
      grid.appendChild(cell);
    });

    months.appendChild(el('span', '', dateWords(days[0].day)));
    months.appendChild(el('span', '', dateWords(days[days.length - 1].day)));
    if (note) note.textContent = data.note || '';
    if (caption) {
      caption.textContent = '';
      caption.appendChild(document.createTextNode(
        int(data.n) + ' settled over ' + days.length + ' days'));
      if (state.calendarDay) {
        const clear = el('button', 'cal-clear', 'show the whole season');
        clear.type = 'button';
        clear.addEventListener('click', () => {
          state.calendarDay = null;
          state.historyOffset = 0;
          renderResults().catch(showError);
        });
        caption.appendChild(clear);
      }
    }
  }

  // "2026-09-01" -> "1 Sep". The calendar's month strip only.
  function dateWords(iso) {
    if (!iso) return '';
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
  }

  // SETTINGS (GRIDIRON_13 P3).
  //
  // EVERY LABEL, EVERY REASON AND EVERY REFUSAL IS THE SERVER'S. This places
  // controls and posts values; it decides nothing about what may be changed.
  // The fence lives in `settings.EDITABLE`, so a control that should not
  // exist cannot be created by editing this file.
  let csrfToken = null;

  async function renderSettings() {
    const data = await fetchJSON('/api/settings');
    csrfToken = data.csrf || csrfToken;
    document.getElementById('settings-caption').textContent =
      int(data.n) + ' settings you can change';

    const host = document.getElementById('settings-sections');
    host.innerHTML = '';
    (data.sections || []).forEach(section => {
      const panel = el('section', 'panel');
      panel.appendChild(el('h3', '', section.name));
      section.settings.forEach(s => panel.appendChild(settingRow(s)));
      host.appendChild(panel);
    });

    renderAccess(data.access);
    renderHealthPanel(data.health);
    renderFenced(data);
    renderRulings(data.rulings);
    renderRecentChanges(data.recent);
  }

  function settingRow(s) {
    const row = el('div', 'set');
    const key = el('div', 'set-k');
    key.appendChild(el('b', '', s.label));
    key.appendChild(el('small', '', s.why || ''));
    // WHEN THE APP AND THE SCHEDULER DISAGREE, the sentence sits with the
    // control rather than in a banner elsewhere on the page.
    if (s.disagreement) key.appendChild(el('div', 'set-warn', s.disagreement));
    row.appendChild(key);

    const val = el('div', 'set-v');
    let input;
    if (s.kind === 'switch') {
      input = el('button', 'set-switch');
      input.type = 'button';
      const on = s.value === '1';
      input.textContent = on ? 'on' : 'off';
      input.setAttribute('aria-pressed', String(on));
      input.addEventListener('click', () => {
        const next = input.getAttribute('aria-pressed') === 'true' ? '0' : '1';
        saveSetting(s.name, next, row);
      });
    } else {
      input = el('input', 'inp');
      input.value = s.value;
      input.setAttribute('aria-label', s.label);
      input.addEventListener('change', () => saveSetting(s.name, input.value, row));
    }
    val.appendChild(input);
    if (s.kind === 'hour') val.appendChild(document.createTextNode(' :00 local'));
    else if (s.kind === 'time') val.appendChild(document.createTextNode(' local'));
    row.appendChild(val);
    return row;
  }

  async function saveSetting(name, value, row) {
    let said = row.querySelector('.set-said');
    if (!said) { said = el('div', 'set-said'); row.appendChild(said); }
    said.textContent = 'saving...';
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json',
                   'X-Gridiron-Form': csrfToken || '' },
        body: JSON.stringify({ name: name, value: value }),
      });
      const body = await res.json();
      if (!res.ok) {
        // THE SERVER'S OWN WORDS. It refuses a model constant and says why;
        // inventing a friendlier message here would hide which rule stopped
        // it, and the reason is the whole point of the fence.
        said.textContent = body.detail || 'that change was not recorded';
        return;
      }
      said.textContent = body.line || 'saved';
      // THE FACE FOLLOWS THE SAVE (UI audit finding 5, 2026-09-05). The line
      // said "changed from 1 to 0" while the switch still read "on"; a second
      // click said "is already 0" and it still read "on".
      const control = row.querySelector('.set-switch, input.inp');
      const saved = (body.value === undefined || body.value === null) ? String(value) : String(body.value);
      if (control && control.classList.contains('set-switch')) {
        const on = saved === '1';
        control.textContent = on ? 'on' : 'off';
        control.setAttribute('aria-pressed', String(on));
      } else if (control) {
        control.value = saved;
      }
      renderRecentChanges(body.recent);
    } catch (err) {
      said.textContent = 'the change did not reach the appliance';
    }
  }

  function renderAccess(access) {
    const host = document.getElementById('settings-access');
    if (!host || !access) return;
    host.innerHTML = '';
    ['token', 'topic'].forEach(k => {
      const a = access[k];
      if (!a) return;
      const row = el('div', 'set');
      const key = el('div', 'set-k');
      key.appendChild(el('b', '', a.label));
      key.appendChild(el('small', '', a.why));
      row.appendChild(key);
      const val = el('div', 'set-v');
      // MASKED, NEVER SHOWN. The server sends four characters at each end and
      // the length; it does not send the secret.
      val.appendChild(el('code', '', a.masked));
      // A COMMAND THE OPERATOR TYPES, marked as the literal it is. The
      // plain-words scan excludes sanctioned code by POSITION, and a rotate
      // command must be reproduced exactly or it does not work.
      const how = el('div', 'set-how');
      how.appendChild(document.createTextNode('rotate: '));
      how.appendChild(el('code', 'code-literal', a.how));
      val.appendChild(how);
      row.appendChild(val);
      host.appendChild(row);
    });
    // SIGN OUT EVERYWHERE. The other half of a thirty-day sliding session:
    // it does not expire while it is in use, so a device left signed in stays
    // signed in, and the app has to offer a way to end that without needing
    // the token to hand.
    const out = el('div', 'set');
    const outKey = el('div', 'set-k');
    outKey.appendChild(el('b', '', 'Sign out everywhere'));
    outKey.appendChild(el('small', '',
      'Ends every session on every device, including this one.'));
    out.appendChild(outKey);
    const outVal = el('div', 'set-v');
    const outBtn = el('button', 'set-switch', 'sign out');
    outBtn.type = 'button';
    outBtn.addEventListener('click', async () => {
      const said = el('div', 'set-said');
      out.appendChild(said);
      said.textContent = 'signing out...';
      try {
        const res = await fetch('/auth/logout?everywhere=true', {
          method: 'POST', headers: { 'X-Gridiron-Form': csrfToken || '' } });
        const body = await res.json();
        said.textContent = body.line || 'signed out';
        setTimeout(() => { location.href = '/login'; }, 900);
      } catch (err) {
        said.textContent = 'that did not reach the appliance';
      }
    });
    outVal.appendChild(outBtn);
    out.appendChild(outVal);
    host.appendChild(out);

    if (access.build && access.build.line) {
      host.appendChild(el('div', 'set-how', 'this build: ' + access.build.line));
    }
  }

  // HEALTH IS THE SCHEDULE PANEL'S DATA, drawn by the schedule panel's own
  // renderer. One implementation with the rail notices, as P3 requires: a
  // second one would be a second opinion about whether a task is late.
  function renderHealthPanel(health) {
    const host = document.getElementById('settings-health');
    if (!host) return;
    host.innerHTML = '';
    if (!health) return;
    (health.tasks || []).forEach(t => {
      const row = el('div', 'set');
      const key = el('div', 'set-k');
      key.appendChild(el('b', '', t.task_label || t.task));
      key.appendChild(el('small', '', t.what || ''));
      // A TASK THAT HAS GONE QUIET SAYS SO, and a missed slate is named
      // rather than counted. Weight and position, never red: a late task is
      // not a pick that lost (GRIDIRON_16 R2).
      // THE SERVER'S OWN WARNING, placed. It reads "has never run. If the
      // scheduler is installed, it has not fired yet; if it is not, nothing
      // is running." -- which is the sentence that makes a blank row read as
      // "nothing is running" instead of "fine".
      if (t.warning) key.appendChild(el('div', 'set-warn', t.warning));
      (t.missed || []).forEach(m => key.appendChild(el('div', 'set-warn',
        typeof m === 'string' ? m : (m.line || ''))));
      row.appendChild(key);

      const val = el('div', 'set-v');
      // EVERY CELL COMES FROM `task_runs`. No string on this page is copied
      // out of the mockup: `last_result` is what the run recorded, and
      // `last_detail` is what it said about itself.
      val.appendChild(el('code', '', t.last_result || 'never run'));
      // ALWAYS BOTH LINES, EVEN WHEN THERE IS NOTHING TO PUT IN THEM. These
      // were written only when a timestamp existed, so a task that had never
      // run showed no "last ran" line at all -- and an absent line reads as
      // "no information" where "last ran: never" is a fact. That is the same
      // failure a blank row makes: it reads as fine.
      val.appendChild(el('div', 'set-how',
        'last ran ' + (t.last_run_utc ? localDateTime(t.last_run_utc) : 'never')));
      val.appendChild(el('div', 'set-how',
        'next due ' + (t.next_due_utc ? localDateTime(t.next_due_utc)
                                      : 'not scheduled')));
      if (t.last_detail) {
        val.appendChild(el('div', 'set-how', t.last_detail));
      }
      row.appendChild(val);
      host.appendChild(row);
    });
    // STALENESS PER SPORT, side by side and never summed (LAW 6). The
    // server already says so in `side_by_side_sports`; this places its notes.
    ((health.schedule_staleness || {}).sports || []).forEach(sp => {
      const row = el('div', 'set-how health-stale');
      row.appendChild(el('b', '', sp.label || sp.sport));
      row.appendChild(document.createTextNode(' ' + (sp.note || '')));
      host.appendChild(row);
    });
    if (health.live_poll && health.live_poll.line) {
      host.appendChild(el('div', 'set-how', health.live_poll.line));
    }
    // THE LAST NOTIFICATION AND WHETHER IT ARRIVED. A push that silently
    // failed is worse than no push channel, because the operator believes
    // they are covered -- so the channel results are shown, not just the fact
    // that something was sent.
    const last = health.last_notification;
    if (last) {
      const channels = (last.channels || [])
        .map(c => c.channel + ' ' + (c.ok ? 'delivered' : 'failed: ' + (c.detail || '')))
        .join(' · ');
      host.appendChild(el('div', 'set-how',
        'last message (' + (last.state || '') + '): ' + (last.body || '') +
        (channels ? ' — ' + channels : '')));
    }
  }

  function renderFenced(data) {
    const host = document.getElementById('settings-fenced');
    const note = document.getElementById('settings-fenced-note');
    if (!host) return;
    if (note) note.textContent = data.fenced_note || '';
    host.innerHTML = '';
    (data.fenced || []).forEach(f => {
      const row = el('div', 'set set-fenced');
      const key = el('div', 'set-k');
      key.appendChild(el('b', '', f.label));
      key.appendChild(el('small', '', f.what));
      row.appendChild(key);
      const val = el('div', 'set-v');
      // READ-ONLY, AND NOT AN INPUT AT ALL. A disabled text box invites a
      // reader to go looking for the thing that would enable it.
      //
      // A `literal` value is an identifier a reader must be able to match
      // against a stored one -- the factor set version is stamped on every
      // prediction -- so it is marked as sanctioned code rather than
      // paraphrased into something that would not match.
      val.appendChild(el('code', f.literal ? 'code-literal' : '', f.value));
      val.appendChild(el('div', 'set-how', 'declared ' + (f.declared || '')));
      row.appendChild(val);
      host.appendChild(row);
    });
  }

  function renderRulings(rulings) {
    const host = document.getElementById('settings-rulings');
    if (!host) return;
    host.innerHTML = '';
    (rulings || []).forEach(r => {
      const row = el('div', 'set set-fenced');
      const key = el('div', 'set-k');
      key.appendChild(el('b', '', r.name));
      key.appendChild(el('small', '', r.what));
      row.appendChild(key);
      host.appendChild(row);
    });
  }

  function renderRecentChanges(recent) {
    const host = document.getElementById('settings-recent');
    const count = document.getElementById('settings-recent-n');
    if (!host) return;
    host.innerHTML = '';
    if (count) count.textContent = (recent || []).length + ' recorded';
    if (!(recent || []).length) {
      host.appendChild(el('div', 'empty', 'Nothing has been changed yet.'));
      return;
    }
    recent.forEach(c => {
      const row = el('div', 'change');
      row.appendChild(el('span', 'change-when', localDateTime(c.when)));
      row.appendChild(el('span', '', c.label + ': ' +
        (c.previous ? c.previous + ' → ' : '') + c.value));
      if (c.note) row.appendChild(el('span', 'change-note', ' ' + c.note));
      host.appendChild(row);
    });
  }

  function localDateTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString();
  }

  // THE SETTLED CARDS (S3). The same card the pick was born on, in its
  // third state. Fetched from the slate payload rather than the history
  // table, because a card is a card and a table row is a row.
  async function renderSettledCards() {
    const host = document.getElementById('results-settled');
    const headingRow = document.getElementById('settled-heading-row');
    const heading = document.getElementById('settled-heading');
    if (!host) return;
    host.innerHTML = '';
    let data = null;
    try {
      // The current slate, which is what the week picker is pointing at.
      // No forecaster or tier arguments: the settled cards are the day's, and
      // the day strip on Picks is where a filter is named.
      const picked = document.getElementById('week-picker');
      const chosen = picked && picked.value ? JSON.parse(picked.value) : null;
      const qs = chosen
        ? '?season=' + chosen.season + '&week=' + chosen.week : '';
      data = await fetchJSON(withSport('/api/week' + qs));
    } catch (err) {
      host.hidden = true;
      if (headingRow) headingRow.hidden = true;
      return;
    }
    const today = (data && data.today) || {};
    const cards = today.settled || [];
    const labels = today.labels || {};
    cards.forEach(entry => host.appendChild(todayCard(entry, labels)));
    host.hidden = !cards.length;
    if (headingRow) headingRow.hidden = !cards.length;
    if (heading) heading.textContent = today.settled_heading || '';
  }

  async function renderResults() {
    const seq = sportSeq;
    const data = await fetchJSON(withSport('/api/history?' + historyQuery()));
    if (stale(seq)) return;
    requireN(data, 'history');
    state.historyTotal = data.n;
    // PLACED, NOT COMPOSED. This glued " on " onto a date, which is the
    // renderer writing a sentence -- the thing `check_js_composes_no_prose`
    // exists to refuse. The server says which day it filtered to.
    document.getElementById('history-caption').textContent = data.caption || '';
    await renderSettledCards();
    await renderCalendar();

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
          // The slate in the server's words: "Week 7, 2025", "Saturday 5
          // September". `'wk ' + i.week` put the college key on the page.
          i.slate_label || '',
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


  async function loadSports() {
    const data = await fetchJSON('/api/sports');
    state.sports = data.sports;
    const host = document.getElementById('sport-tabs');
    host.innerHTML = '';
    data.sports.forEach(sp => {
      const b = el('button', '', sp.label);
      // LAW 4 IN THE NAVIGATION, and LAW 6 beside it: each tab carries its own
      // record and there is no total anywhere. The line and the hover are both
      // written by the server -- this used to glue `sp.label + ': ' + sp.n +
      // ' settled'` together here, which is prose composed in the browser.
      // TWO SPANS, so the trailing word can give way at narrow widths while
      // the count never does. Both strings come from the server; this places
      // them and decides nothing about the wording.
      b.appendChild(el('span', 'tab-n', sp.record_parts[0]));
      if (sp.record_parts[1]) {
        b.appendChild(el('span', 'tab-word', sp.record_parts[1]));
      }
      b.title = sp.record_detail;
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
    // A DAY SELECTED IN ONE SPORT MEANS NOTHING IN ANOTHER (LAW 6). Carrying
    // it across would filter a football table to a baseball date and show an
    // empty page that looks like a missing record.
    state.calendarDay = null;
    state.market = '';
    document.querySelectorAll('#sport-tabs button').forEach(b => {
      const on = b.dataset.sport === sport;
      b.setAttribute('aria-current', on ? 'true' : 'false');
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    const seq = ++sportSeq;
    try {
      await renderGreeting();
      if (stale(seq)) return;
      const meta = await fetchJSON(withSport('/api/meta'));
      if (stale(seq)) return;
      state.meta = meta;
      renderBanner(state.meta);
      renderColophon(state.meta);
      const scorecard = await fetchJSON(withSport('/api/scorecard'));
      if (stale(seq)) return;
      state.scorecard = scorecard;
      await loadMarkets();
      if (stale(seq)) return;
      await loadWeekPicker();
      if (stale(seq)) return;
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

    // THE OPERATOR'S OWN RESULTS, on their own line beneath the model's.
    // Placed, not composed: `calls.line` is None when nothing of theirs has
    // settled, and an absent line is an absent line rather than "0 right".
    if (data.calls && data.calls.line) {
      msg.appendChild(el('br'));
      msg.appendChild(el('span', 'greet-calls', data.calls.line));
    }

    const counts = hosts.countdown;
    if (counts) {
      counts.textContent = (data.movement.buckets[0] || {}).countdown ||
        (data.today && data.today.line) || '';
      counts.hidden = !counts.textContent;
    }

    // THE NOTICES BAR IS GONE (THREE_STATES S1, 2026-09-08). A fault
    // belongs on the Health panel, which is where these still are; what the
    // strip cost was the top of the screen the operator opens.

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
  // `shortNotice` stood here for the notices bar THREE_STATES removed;
  // nothing called it. Removed by NIGHT_AUDIT item 6, 2026-09-08.

  async function renderGreeting() {
    const strip = document.getElementById('glance');
    if (!strip) return;
    try {
      const seq = sportSeq;
      const data = await fetchJSON(withSport('/api/digest'));
      if (stale(seq)) return;
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
  // NOTHING TO APPLY. `applyDeskClass` put a `desk-on` class on the body so
  // the stylesheet could tell which of two layouts the renderer had built, and
  // a media-query listener re-rendered the slate whenever the breakpoint was
  // crossed because CROSSING IT CHANGED WHICH ELEMENTS EXIST. One layout means
  // crossing a width changes how things look and never what they are, which is
  // what a stylesheet is for.
  function applyDeskClass() {
    placeGreeting();
  }
  // `deskKeys` WENT WITH THE DESK. It moved a selection between tiles with
  // the arrow keys, which was the desk's own affordance -- a listbox of tiles
  // beside a rail that showed whichever was selected. A grid of cards that
  // each expand in place needs no selection to move: every card is a button
  // and the browser's own tab order already walks them.

  //: Where a renamed route now lives. A redirect rather than a second entry
  //: in ROUTES, so there is exactly one name for the page and the address bar
  //: says which one it is.
  //: FOUR PAGES (GRIDIRON_13 P5), and every old address still lands.
  //:
  //: `factors` and `versions` were two more places to go and one more
  //: decision about where a thing lived; both were about the same subject --
  //: what the model is and what changed -- and both are sections of Record
  //: now. `schedule` became Settings > Health. `digest` went: the greeting
  //: keeps its data, and a particular day is a filter on Results.
  //:
  //: REDIRECTS, NOT 404s. A link somebody bookmarked or wrote down still
  //: works, and the address bar says where the page went.
  const RENAMED = {
    history: 'results',
    factors: 'record',
    versions: 'record',
    schedule: 'settings',
    digest: 'week',
  };

  const ROUTES = {
    record: renderRecord,
    week: renderWeek,
    // RESULTS, renamed from History on 2026-09-02 (GRIDIRON_16 R4). Settled
    // rows live here and only here; Picks no longer carries a resolved
    // section. `#/history` still resolves -- see the redirect in `route`.
    results: renderResults,
    settings: renderSettings
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
      const msg = document.getElementById('greet-msg');
      if (msg) msg.hidden = !home;
      greeting.hidden = !home || greeting.dataset.empty === 'true';
    }
    const settled = document.getElementById('greet-settled');
    if (settled) settled.hidden = !home;
  }

  async function route() {
    clearError();
    // PICKS IS THE LANDING PAGE (GRIDIRON_13 P6). The first question on
    // opening a forecaster is what it says about tonight, not how it did.
    let name = (location.hash.replace('#/', '') || 'week');
    // OLD ROUTES REDIRECT, they do not 404 (R4). A link somebody bookmarked
    // or a note they wrote down still lands where the page went.
    if (RENAMED[name]) {
      location.replace('#/' + RENAMED[name]);
      return;
    }
    const view = ROUTES[name] ? name : 'week';
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
    const seq = sportSeq;
    try {
      await loadSports();
      await renderGreeting();
      const meta = await fetchJSON(withSport('/api/meta'));
      if (!stale(seq)) {
        state.meta = meta;
        renderBanner(state.meta);
        renderColophon(state.meta);
      }
      const scorecard = await fetchJSON(withSport('/api/scorecard'));
      if (!stale(seq)) state.scorecard = scorecard;
      if (!stale(seq)) await loadMarkets();
      if (!stale(seq)) await loadWeekPicker();
    } catch (err) {
      showError(err);
    }

    wireSortToggle();
    // THE DIGEST'S DAY PICKER went with the page (P5). Choosing a particular
    // day is now a click on the Results calendar, which shows the same day's
    // record with its balance rather than making a reader type a date.
    window.addEventListener('hashchange', route);
    ['chart-market', 'chart-predictor'].forEach(id =>
      document.getElementById(id).addEventListener('change', () => {
        try { renderRecord(); } catch (err) { showError(err); }
      }));
    document.getElementById('tier-market').addEventListener('change', () =>
      refreshTierTable().catch(showError));
    document.getElementById('week-picker').addEventListener('change', () =>
      renderWeek().catch(showError));
    document.getElementById('week-market').addEventListener('change', event => {
      state.market = event.target.value || '';
      renderWeek().catch(showError);
    });
    ['history-q', 'history-market', 'history-predictor', 'history-outcome'].forEach(id =>
      document.getElementById(id).addEventListener('input', () => {
        state.historyOffset = 0;
        renderResults().catch(showError);
      }));
    document.getElementById('history-prev').addEventListener('click', () => {
      state.historyOffset = Math.max(0, state.historyOffset - 100);
      renderResults().catch(showError);
    });
    document.getElementById('history-next').addEventListener('click', () => {
      state.historyOffset += 100;
      renderResults().catch(showError);
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
