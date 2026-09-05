"""The league's own day (ruling 3 on the audit, 2026-09-05)."""
from __future__ import annotations

import pytest

from gridiron import db
from gridiron.data import cfb_loader, reference
from gridiron.sports import ufc as ufc_sport


def test_a_late_college_kickoff_is_still_saturday():
    assert reference.league_day("cfb", "2026-09-06T02:30:00Z") == "2026-09-05"
    assert reference.league_day("cfb", "2026-09-05T16:00:00Z") == "2026-09-05"
    assert reference.slate_key("2026-09-05") == 20260905


def test_a_las_vegas_card_that_ends_after_midnight_utc_is_saturday():
    assert reference.league_day("ufc", "2026-09-06T03:00Z",
                                country="USA", state="NV") == "2026-09-05"


def test_the_events_own_zone_decides_not_eastern():
    assert reference.league_day("ufc", "2026-09-05T16:00Z",
                                country="United Arab Emirates") == "2026-09-05"
    assert reference.league_day("ufc", "2026-09-05T21:00Z",
                                country="Australia", state="WA") == "2026-09-06"


def test_an_undeclared_venue_is_absent_not_guessed():
    assert reference.league_day("ufc", "2026-09-06T03:00Z", country="Atlantis") is None
    assert reference.league_day("ufc", "2026-09-06T03:00Z") is None
    assert reference.league_day("cfb", None) is None


def test_the_convention_is_dated_and_refuses_an_unknown_sport():
    assert reference.LEAGUE_DAY_DECLARED == "2026-09-05"
    with pytest.raises(ValueError):
        reference.league_day("curling", "2026-09-05T16:00:00Z")


def test_the_college_slate_key_follows_the_eastern_day():
    assert cfb_loader._slate_ordinal({"date": "2026-09-06T02:30Z"}) == 20260905
    assert cfb_loader._slate_ordinal({"date": "2026-09-05T16:00Z"}) == 20260905
    assert cfb_loader._slate_ordinal({}) == 0


def test_the_mirror_keys_a_card_by_its_local_date(conn):
    conn.execute(
        "INSERT INTO ufc_events (id, name, event_utc, season, fetched_utc,"
        " event_tier, is_card, venue_country, venue_state, venue_city)"
        " VALUES ('vegas','UFC Fight Night: Las Vegas','2026-09-06T01:00Z',2026,?,"
        " 'fight_night',1,'USA','NV','Las Vegas')", (db.utcnow(),))
    conn.execute(
        "INSERT INTO ufc_events (id, name, event_utc, season, fetched_utc,"
        " event_tier, is_card) VALUES ('nowhere','UFC Fight Night: Nowhere',"
        " '2026-09-13T01:00Z',2026,?,'fight_night',1)", (db.utcnow(),))
    for who in ("A", "B", "C", "D"):
        conn.execute("INSERT INTO ufc_fighters (id, name, fetched_utc) VALUES (?,?,?)",
                     (who, f"Fighter {who}", db.utcnow()))
    conn.execute(
        "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
        " fighter_a, fighter_b, status, fetched_utc)"
        " VALUES ('v1','vegas','2026-09-06T03:00Z',3,'A','B','scheduled',?)", (db.utcnow(),))
    conn.execute(
        "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
        " fighter_a, fighter_b, status, fetched_utc)"
        " VALUES ('n1','nowhere','2026-09-13T03:00Z',3,'C','D','scheduled',?)", (db.utcnow(),))
    conn.commit()
    ufc_sport.mirror_bouts(conn)
    vegas = conn.execute("SELECT week, league_date FROM games WHERE id = 'v1'").fetchone()
    assert (vegas["week"], vegas["league_date"]) == (20260905, "2026-09-05")
    nowhere = conn.execute("SELECT week, league_date FROM games WHERE id = 'n1'").fetchone()
    assert (nowhere["week"], nowhere["league_date"]) == (20260913, "2026-09-13"), (
        "an undeclared venue falls back to the UTC day, and says so")
    assert ufc_sport.mirror_bouts.undated == 1
