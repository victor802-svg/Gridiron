"""THE RECORD PAGE'S TWO CHART PANELS (visual pass, 2026-09-25): the closing
line over time and the taken / passed over / all curves, per sport and per
market, drawn only past their gate, never merged."""
from __future__ import annotations

from gridiron import calibration, config, views

WIDE = {"width": 1300, "height": 900}


def test_the_taken_record_is_three_curves_per_market_behind_one_gate(world_copy):
    sc = views.scorecard(world_copy, "nfl")
    record = sc["taken_record"]
    assert "n" in record and sc["record_words"]["taken_heading"]
    for entry in record["markets"]:
        assert entry["n"] > 0 and entry["gate"] == config.MIN_SAMPLE_FOR_EDGE_CLAIM
        assert entry["market_label"] and "_" not in entry["market_label"]
        for key in ("taken", "not_taken", "all"):
            group = entry[key]
            assert isinstance(group["n"], int) and group["gate_words"].endswith(f"of {entry['gate']}")
            assert "buckets" in group
        assert entry["all"]["n"] == entry["taken"]["n"] + entry["not_taken"]["n"], "the three curves are one population split, never a sum shown as more"
    calibration.assert_every_figure_has_n(record)


def test_the_closing_line_carries_a_series_only_past_its_floor(world_copy):
    line = calibration.clv_report(world_copy, sport="nfl")
    for entry in line["markets"]:
        assert entry["gate_words"] == f"{entry['n']} of {entry['minimum_for_a_claim']}"
        if entry["renderable"]:
            assert len(entry["series"]) == entry["n"]
            assert all(set(p) == {"when", "cents"} for p in entry["series"])
        else:
            assert entry["series"] == []


def test_below_the_gate_the_chart_area_says_the_count_and_draws_nothing(page):
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/record'")
    page.wait_for_selector("#taken-record:not([hidden])", timeout=20000)
    empties = page.evaluate("[...document.querySelectorAll('#taken-record .chart-empty')].map(e => e.textContent)")
    assert empties and all(" of 100" in e for e in empties), empties
    assert page.evaluate("document.querySelectorAll('#taken-record canvas').length") == 0
    # the drawer itself, on a synthetic series past its floor: it draws ink
    inked = page.evaluate("""() => {
        const c = document.createElement('canvas'); c.width = 300; c.height = 120;
        document.body.appendChild(c);
        Gridiron.drawSeries(c, { market: 'spread', n: 50, renderable: true,
          series: Array.from({length: 50}, (_, i) => ({ when: '2026-09-' + String(1 + (i % 28)).padStart(2, '0') + 'T00:00:00Z', cents: (i % 7) - 3 })) });
        const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        let ink = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) ink++;
        c.remove(); return ink; }""")
    assert inked > 200, "the series drawer drew nothing"
    refused = page.evaluate("""() => { try { Gridiron.drawSeries(document.createElement('canvas'), { market: 'spread', series: [] }); return 'drew'; } catch (e) { return e.message; } }""")
    assert "LAW 4" in refused, refused
