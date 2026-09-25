"""The prompt record (the ruling of 2026-09-24, two additions, item 1, and the
ruling on question 4, 2026-09-25).

"The reasoning pass stores the exact prompt it sent ... with every row it
writes, append-only. No reasoning row may exist without it." "The
prompt-record rule binds from the release that ships it, and the gap before
it is labelled, not exempted." These hold the one door, the release instant,
the schema's refusals, the reconstruction tool and the words on the page to
those sentences, on scratch worlds only.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gridiron import audit, config, db, language, run, views
from gridiron.factors import compute, store
from gridiron.model import activation, baseline, llm, predict, prompt_record
from tests.conftest import seed_a_sent_prompt
from tests.test_predict import StubClient

REPO = Path(__file__).resolve().parents[1]


def _load_the_tool():
    """The tool, by its path, so `tools/` is never put ahead of anything on
    the import path."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gridiron_reconstruct_prompts", REPO / "tools" / "reconstruct_prompts.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reconstruct_prompts = _load_the_tool()

ANSWER = '{"probability": 0.66, "reasoning": "The home rating is better."}'


@pytest.fixture
def trained(league):
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="test")
    activation.activate_in_a_scratch_world(league)
    return league


# ---------------------------------------------------------------------------
# the release instant
# ---------------------------------------------------------------------------

def test_the_release_instant_is_written_once_and_never_moves(conn):
    instant = prompt_record.binds_from(conn)
    assert instant and len(instant) == 20 and instant.endswith("Z")
    db.init(conn)
    assert prompt_record.binds_from(conn) == instant, "a second open moved it"
    for sql, args in (
            ("UPDATE meta SET value = ? WHERE key = ?",
             ("2020-01-01T00:00:00Z", prompt_record.BINDS_FROM)),
            ("DELETE FROM meta WHERE key = ?", (prompt_record.BINDS_FROM,)),
            ("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
             (prompt_record.BINDS_FROM, "2020-01-01T00:00:00Z")),
            ("UPDATE meta SET key = ? WHERE key = 'kind'",
             (prompt_record.BINDS_FROM,))):
        with pytest.raises(Exception) as refused:
            conn.execute(sql, args)
        conn.rollback()
        assert "GRIDIRON PROMPT RECORD" in str(refused.value), sql
    assert prompt_record.binds_from(conn) == instant


def test_the_instant_is_never_before_a_reasoning_row_already_written():
    """Written by the first open under the schema: now, or one second after
    the newest reasoning row if a scheduled task wrote one in that second."""
    conn = db.connect(":memory:")
    conn.executescript(db.SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO games (id, sport, season, week, game_type, home,"
                 " away, status) VALUES ('g', 'mlb', 2026, 1, 'R', 'A', 'B',"
                 " 'scheduled')")
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning) VALUES ('2099-01-01T00:00:00Z', 'mlb', 'g',"
        " 'moneyline', 'A', 0.6, 'win', 'llm', 'fs2', '{}', 'r')")
    conn.commit()
    assert prompt_record.write_the_release_instant(conn) == "2099-01-01T00:00:01Z"
    with pytest.raises(Exception, match="GRIDIRON PROMPT RECORD"):
        conn.execute("INSERT INTO meta (key, value) VALUES (?, 'not a time')",
                     (prompt_record.BINDS_FROM,))


# ---------------------------------------------------------------------------
# the one door, and the prompt as sent
# ---------------------------------------------------------------------------

def test_every_reasoning_row_carries_the_request_the_client_received(trained):
    """Byte for byte: the stored request is the canonical form of exactly the
    keywords the client was called with, and its hash names those bytes."""
    client = StubClient([ANSWER] * 40)
    run.run_week(trained, 2025, 7, include_props=False, use_llm=True,
                 llm_client=client)
    rows = trained.execute(
        "SELECT id, game_id, factors_json FROM predictions"
        " WHERE predictor = 'llm' ORDER BY id").fetchall()
    assert len(rows) == 4 == len(client.requests)
    records = prompt_record.records_for(trained, [r["id"] for r in rows])
    calls = [c[0] for c in trained.execute(
        "SELECT id FROM llm_calls WHERE purpose = 'reasoning' ORDER BY id")]
    for row, received, call in zip(rows, client.requests, calls):
        record = records[row["id"]]
        assert record["kind"] == "sent"
        assert record["request_json"] == prompt_record.canonical(received)
        assert record["request_sha256"] == prompt_record.digest(
            prompt_record.canonical(received))
        assert json.loads(record["request_json"]) == received
        assert received["system"] == llm.SYSTEM_PROMPT
        assert received["max_tokens"] == config.LLM_MAX_OUTPUT_TOKENS
        assert record["game_id"] == row["game_id"]
        assert record["llm_call_id"] == call
        payload = json.loads(row["factors_json"])
        assert payload[prompt_record.CITE] == record["id"]
        assert record["claim"] == payload["question"]["claim"]
    assert audit.prompt_record_faults(trained) == []


def test_the_reformatting_request_is_kept_with_the_prompt(conn):
    client = StubClient(["I think about 0.7, honestly.",
                         '{"probability": 0.7, "reasoning": "Recovered."}'])
    result = llm.reason(conn, question="KC covers -3.5", factor_rows=[],
                        notes=[], game_id="G1", client=client)
    assert result.repaired
    assert result.prompt.request_json == prompt_record.canonical(client.requests[0])
    assert result.prompt.repair_json == prompt_record.canonical(client.requests[1])
    assert json.loads(result.prompt.repair_json)["messages"][0]["content"] \
        == "I think about 0.7, honestly."


def test_a_reasoning_row_without_its_prompt_is_refused_by_name(trained):
    run.run_week(trained, 2025, 7, include_props=False, use_llm=False)
    q = _a_question(trained)
    fv = compute.FeatureVector(sport="nfl", market_type="spread")
    before = trained.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    with pytest.raises(prompt_record.PromptNotKept, match="THE PROMPT IT WAS SENT"):
        predict.write_prediction(trained, q, predictor="llm", prob_yes=0.6,
                                 fv=fv, reasoning="r", final=True)
    assert trained.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == before


def test_a_refused_row_leaves_no_prompt_behind(trained):
    """The record and the row exist together or not at all: a row the
    schema refuses takes its freshly written prompt record with it."""
    run.run_week(trained, 2025, 7, include_props=False, use_llm=False)
    q = _a_question(trained)
    fv = compute.FeatureVector(sport="nfl", market_type="spread")
    # A prompt "sent" after its row is written is refused by the trigger.
    late = prompt_record.sent(llm.reasoning_request("CLAIM: " + q.claim),
                              sent_utc="2099-01-01T00:00:00Z")
    with pytest.raises(Exception, match="GRIDIRON PROMPT RECORD"):
        predict.write_prediction(trained, q, predictor="llm", prob_yes=0.6,
                                 fv=fv, reasoning="r", final=True, prompt=late)
    assert trained.execute("SELECT COUNT(*) FROM reasoning_prompts").fetchone()[0] == 0
    assert not trained.in_transaction


def test_the_door_refuses_a_request_that_is_not_one_canonical_request(conn, monkeypatch):
    request = llm.reasoning_request("CLAIM: x")
    for text in (json.dumps(request),                       # not canonical
                 prompt_record.canonical({"model": "m"}),   # not a request
                 prompt_record.canonical(dict(request, temperature=1))):
        with pytest.raises(prompt_record.PromptNotKept):
            prompt_record.keep_sent(
                conn, prompt_record.SentPrompt(text, db.utcnow()),
                game_id="g", claim="x")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-planted-secret-value")
    leaked = llm.reasoning_request("CLAIM: x sk-planted-secret-value")
    with pytest.raises(prompt_record.PromptNotKept, match="secret"):
        prompt_record.keep_sent(conn, prompt_record.sent(leaked),
                                game_id="g", claim="x")


def _a_question(conn):
    """A question of the written slate, as the sport's own door forms it."""
    from gridiron import sports

    return next(iter(sports.get("nfl").slate_questions(
        conn, 2025, 7, include_props=False)))


# ---------------------------------------------------------------------------
# the reconstruction
# ---------------------------------------------------------------------------

def _head() -> str:
    return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def _old_reasoning_rows(conn, n=2) -> list[int]:
    """Reasoning rows written 'before the release': copies of statistical
    rows under the other forecaster, dated before the world's instant, as the
    late pass (so an early reasoning row of the same question can stand)."""
    stat = conn.execute(
        "SELECT * FROM predictions WHERE predictor = 'statistical'"
        " ORDER BY id LIMIT ?", (n,)).fetchall()
    ids = []
    for row in stat:
        payload = json.loads(row["factors_json"])
        payload["llm_model"] = "claude-sonnet-4-5"
        cur = conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning)"
            " VALUES ('2025-10-01T00:00:00Z',?,?,?,?,?,?,?,'llm','final',?,?,'r')",
            (row["sport"], row["game_id"], row["market_type"], row["subject"],
             row["line_asked"], row["model_prob"], row["model_side"],
             row["factor_set_version"], json.dumps(payload)))
        ids.append(cur.lastrowid)
    conn.commit()
    return ids


def test_the_reconstruction_rebuilds_each_row_through_its_commits_own_code(
        trained, db_path):
    run.run_week(trained, 2025, 7, include_props=False, use_llm=False)
    ids = _old_reasoning_rows(trained)
    assert len(audit.prompt_record_faults(trained)) == 2, \
        "two rows with no record at all, before the reconstruction"
    head = _head()
    entry = reconstruct_prompts.ReflogEntry(
        datetime(2025, 1, 1, tzinfo=timezone.utc), head, "planted history")
    report = reconstruct_prompts.reconstruct(db_path, entries=[entry])
    assert report.written == 2 and report.considered == 2
    assert dict(report.by_commit) == {head: ids}
    records = prompt_record.records_for(trained, ids)
    for pid in ids:
        record = records[pid]
        assert record["kind"] == "reconstructed" and record["code_version"] == head
        payload = json.loads(trained.execute(
            "SELECT factors_json FROM predictions WHERE id = ?", (pid,)).fetchone()[0])
        fv = compute.FeatureVector(
            sport=payload["sport"], market_type=payload["market_type"],
            values=dict(payload["values"]), absent=list(payload["absent"]),
            notes=list(payload["notes"]), sources=dict(payload["sources"]),
            failed=dict(payload["failed"]))
        expected = llm.build_prompt(payload["question"]["claim"],
                                    compute.describe(fv), fv.notes)
        request = json.loads(record["request_json"])
        assert request["messages"][0]["content"] == expected
        assert request["model"] == "claude-sonnet-4-5"
        assert request["system"] == llm.SYSTEM_PROMPT
        assert "Until the evening of 23 September" in record["provenance"]
        assert "No scheduled task was recorded" in record["provenance"]
        assert audit.plain_words_violations(record["provenance"]) == []
    assert audit.prompt_record_faults(trained) == []
    # WHAT THE RUN PRINTS (2026-09-25): each commit's caveats, and the
    # coverage it left behind.
    lines = "\n".join(report.lines())
    assert (f"{head[:12]}     2 forecasts, ids {ids[0]}-{ids[1]}; the record says "
            f"2 {reconstruct_prompts.CAVEAT_WORKING_TREE}, "
            f"2 {reconstruct_prompts.CAVEAT_NO_TASK_RUN}") in lines, lines
    assert ("after this run: 2 of 2 reasoning forecasts carry a prompt record "
            "(0 sent, 2 reconstructed)") in lines, lines
    assert report.without == [] and report.committed_after == {}
    again = reconstruct_prompts.reconstruct(db_path, entries=[entry])
    assert again.written == 0 and again.considered == 0, "not idempotent"
    assert again.forecasts == 2 and again.without == []


def test_a_rebuilt_row_committed_after_the_release_is_named(trained, db_path):
    """Dated before the instant, fingerprinted after it -- committed after the
    release, round the door or by old code racing it -- or above the
    fingerprint baseline with no fingerprint at all. The run rebuilds each
    (by its date it is before the release) and names it (2026-09-25, the
    rehearsal of item 4; refusing it is open in FOLLOWUPS)."""
    from gridiron import fingerprint

    run.run_week(trained, 2025, 7, include_props=False, use_llm=False)
    stat = trained.execute("SELECT * FROM predictions WHERE predictor = 'statistical'"
                           " ORDER BY id LIMIT 1").fetchone()
    payload = json.loads(stat["factors_json"])
    payload["llm_model"] = "claude-sonnet-4-5"
    late = config.RECORD_BASELINE["rows"] + 1
    trained.execute(
        "INSERT INTO predictions (id, created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES (?, '2025-10-01T00:00:00Z',?,?,?,?,?,?,?,'llm','final',?,?,'r')",
        (late, stat["sport"], stat["game_id"], stat["market_type"], stat["subject"],
         stat["line_asked"], stat["model_prob"], stat["model_side"],
         stat["factor_set_version"], json.dumps(payload)))
    fingerprint.write(trained, late)
    trained.commit()
    # And one above the baseline with no fingerprint at all: written round
    # `write_prediction` altogether.
    bare = late + 1
    trained.execute(
        "INSERT INTO predictions (id, created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES (?, '2025-10-01T00:00:00Z',?,?,?,?,?,?,?,'llm','early',?,?,'r')",
        (bare, stat["sport"], stat["game_id"], stat["market_type"], stat["subject"],
         stat["line_asked"], stat["model_prob"], stat["model_side"],
         stat["factor_set_version"], json.dumps(payload)))
    trained.commit()
    entry = reconstruct_prompts.ReflogEntry(
        datetime(2025, 1, 1, tzinfo=timezone.utc), _head(), "planted history")
    report = reconstruct_prompts.reconstruct(db_path, entries=[entry])
    assert report.written == 2
    assert sorted(report.committed_after) == [late, bare]
    assert report.committed_after[bare] == reconstruct_prompts.NO_FINGERPRINT
    assert "REBUILT, BUT COMMITTED AFTER THE RELEASE INSTANT" in "\n".join(report.lines())
    assert reconstruct_prompts.main(["--database", str(db_path)]) == 0, \
        "a second run has nothing left to name"


def test_only_a_task_that_writes_the_sports_forecasts_encloses_one(conn):
    """"No scheduled task was recorded running" is decided by the tasks that
    write the sport's forecasts, and a run never finished counts only until
    its task next started (2026-09-25, the rehearsal of item 4)."""
    enclosed = reconstruct_prompts._enclosed_by_a_task_run
    conn.executemany(
        "INSERT INTO task_runs (task, started_utc, finished_utc, result)"
        " VALUES (?,?,?,?)",
        [("live", "2026-09-20T11:59:00Z", "2026-09-20T12:01:00Z", "ok"),
         ("refresh", "2026-09-20T11:00:00Z", None, "running"),
         ("predict:nfl", "2026-09-20T11:59:00Z", "2026-09-20T12:01:00Z", "ok"),
         ("predict:mlb", "2026-09-21T11:59:00Z", "2026-09-21T12:01:00Z", "ok"),
         ("final:mlb", "2026-09-22T11:59:00Z", None, "running"),
         ("final:mlb", "2026-09-23T19:00:00Z", "2026-09-23T19:05:00Z", "ok")])
    conn.commit()
    assert not enclosed(conn, "2026-09-20T12:00:00Z", "mlb"), \
        "a poll, a refresh or another sport's pass wrote it"
    assert enclosed(conn, "2026-09-21T12:00:00Z", "mlb")
    assert enclosed(conn, "2026-09-22T12:00:00Z", "mlb"), \
        "a run that died after writing still ran"
    assert not enclosed(conn, "2026-09-24T12:00:00Z", "mlb"), \
        "a run never finished ran until its task next started, not for ever"


def _the_gate():
    """`tools/verify.py`, by its path, as `test_the_gate.py` loads it."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gridiron_verify_for_the_prompt_record", REPO / "tools" / "verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_OLD_FACTORS = {"sport": "mlb", "market_type": "moneyline", "values": {},
                "absent": [], "failed": {}, "notes": [], "sources": {},
                "question": {"claim": "AAA (home) beat BBB"},
                "llm_model": "claude-sonnet-4-5"}


def _a_record_with_an_old_reasoning_row(path: Path, *, released: bool) -> int:
    """A stand-in record holding one reasoning row with no prompt record,
    dated long before any instant: opened under this schema (released), or
    only given its tables (not yet released, so no instant)."""
    if released:
        conn = db.open_db(path)
    else:
        conn = db.connect(path)
        conn.executescript(db.SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO games (id, sport, season, week, game_type, home,"
                 " away, status) VALUES ('g', 'mlb', 2026, 1, 'R', 'AAA', 'BBB',"
                 " 'scheduled')")
    pid = conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning) VALUES ('2025-10-01T00:00:00Z', 'mlb', 'g',"
        " 'moneyline', 'AAA', 0.6, 'win', 'llm', 'fs2', ?, 'r')",
        (json.dumps(_OLD_FACTORS),)).lastrowid
    conn.commit()
    assert (prompt_record.binds_from(conn) is not None) == released
    conn.close()
    return pid


def test_the_gate_checks_a_released_record_as_it_holds_it(tmp_path, monkeypatch):
    """After the release the gate rebuilds nothing on its copy, so a row the
    operator's run has not reached -- or one written round the door with an
    earlier date -- fails its check by name (the ruling on question 4: "the
    gate fails by name ... on any row of any date with no record at all").
    Found by the rehearsal of item 4, 2026-09-25."""
    verify = _the_gate()
    record = tmp_path / "gridiron.db"
    pid = _a_record_with_an_old_reasoning_row(record, released=True)
    monkeypatch.setattr(config, "DB_PATH", record)
    try:
        verify._gate_copy_path()
        copy = verify._record_conn()
        assert prompt_record.record_for(copy, pid) is None, "rebuilt on the copy"
        assert [f for f in audit.prompt_record_faults(copy)
                if f.startswith("NO PROMPT RECORD AT ALL")
                and f"reasoning forecast {pid} " in f]
    finally:
        verify._drop_the_gate_copy()


def test_before_the_release_the_gate_rebuilds_its_copy(tmp_path, monkeypatch):
    """Before the release nothing else can show every forecast WILL be
    rebuilt, so the gate's copy is, through the tool, and the record is not."""
    verify = _the_gate()
    import reconstruct_prompts as the_gates_tool   # verify's own, by its name

    record = tmp_path / "gridiron.db"
    pid = _a_record_with_an_old_reasoning_row(record, released=False)
    monkeypatch.setattr(config, "DB_PATH", record)
    monkeypatch.setattr(the_gates_tool, "reflog", lambda checkout=None: [
        the_gates_tool.ReflogEntry(datetime(2025, 1, 1, tzinfo=timezone.utc),
                                   _head(), "planted history")])
    try:
        verify._gate_copy_path()
        copy = verify._record_conn()
        assert (prompt_record.record_for(copy, pid) or {}).get("kind") == "reconstructed"
        assert audit.prompt_record_faults(copy) == []
    finally:
        verify._drop_the_gate_copy()
    untouched = db.read_only(record, "checking the stand-in record was not written")
    try:
        assert prompt_record.binds_from(untouched) is None
        assert "reasoning_prompts" in {r[0] for r in untouched.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert untouched.execute("SELECT COUNT(*) FROM reasoning_prompts").fetchone()[0] == 0
    finally:
        untouched.close()


def test_a_row_after_the_instant_is_never_reconstructed(trained, db_path):
    run.run_week(trained, 2025, 7, include_props=False, use_llm=False)
    stat = trained.execute("SELECT * FROM predictions ORDER BY id LIMIT 1").fetchone()
    payload = json.loads(stat["factors_json"])
    payload[prompt_record.CITE] = seed_a_sent_prompt(
        trained, game_id=stat["game_id"], claim=payload["question"]["claim"])
    pid = trained.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES (?,?,?,?,?,?,?,?,'llm',?,?,?,'r')",
        (db.utcnow(), stat["sport"], stat["game_id"], stat["market_type"],
         stat["subject"], stat["line_asked"], stat["model_prob"],
         stat["model_side"], stat["pass_kind"], stat["factor_set_version"],
         json.dumps(payload))).lastrowid
    trained.commit()
    with pytest.raises(Exception, match="GRIDIRON PROMPT RECORD"):
        prompt_record.keep_reconstructed(
            trained, prediction_id=pid, game_id=stat["game_id"],
            claim=payload["question"]["claim"],
            request_json=prompt_record.canonical(llm.reasoning_request("CLAIM: x")),
            code_version="0" * 40, provenance="x" * 60)


def test_a_cite_that_is_not_the_records_own_number_is_refused(trained):
    """ONE SENT PROMPT, ONE FORECAST, WHATEVER THE SPELLING (the prover of
    item 4, 2026-09-25). A cite stored as the text of an id matched its
    record by the id column's affinity, but the no-other-forecast test and
    the one-forecast index compare cites as stored, so a second forecast
    citing a sent record as text landed beside the first. The schema refuses
    any cite that is not the record's integer id, and the one reader shows no
    record under one -- as the gate's audit already read it."""
    run.run_week(trained, 2025, 7, include_props=False, use_llm=False)
    stat = trained.execute("SELECT * FROM predictions ORDER BY id LIMIT 1").fetchone()
    payload = json.loads(stat["factors_json"])
    claim = payload["question"]["claim"]

    def reasoning_row(created, cite, pass_kind):
        return trained.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning)"
            " VALUES (?,?,?,?,?,?,?,?,'llm',?,?,?,'r')",
            (created, stat["sport"], stat["game_id"], stat["market_type"],
             stat["subject"], stat["line_asked"], stat["model_prob"],
             stat["model_side"], pass_kind, stat["factor_set_version"],
             json.dumps(dict(payload, **{prompt_record.CITE: cite})))).lastrowid

    record = seed_a_sent_prompt(trained, game_id=stat["game_id"], claim=claim)
    first = reasoning_row(db.utcnow(), record, "early")
    trained.commit()
    assert prompt_record.record_for(trained, first)["id"] == record
    for spelled in (str(record), float(record), True):
        with pytest.raises(Exception, match="GRIDIRON PROMPT RECORD"):
            reasoning_row(db.utcnow(), spelled, "final")
        trained.rollback()
    # A forecast of its own with its own record, cited as text, is refused
    # too: the cite is the number the door writes, or nothing.
    own = seed_a_sent_prompt(trained, game_id=stat["game_id"], claim=claim)
    with pytest.raises(Exception, match="GRIDIRON PROMPT RECORD"):
        reasoning_row(db.utcnow(), str(own), "final")
    trained.rollback()
    # Before the instant nothing refuses it -- and nothing reads it as sent:
    # the page and the audit agree that it carries no record.
    old = reasoning_row("2025-10-01T00:00:00Z", str(record), "final")
    trained.commit()
    assert prompt_record.record_for(trained, old) is None
    assert [f for f in audit.prompt_record_faults(trained)
            if f.startswith("NO PROMPT RECORD AT ALL")
            and f"reasoning forecast {old} " in f]
    assert views.prompt_detail(trained, old)["kind"] is None


def test_the_live_record_is_known_by_the_files_identity(tmp_path, monkeypatch):
    record = tmp_path / "record.db"
    conn = db.connect(record)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(config, "DB_PATH", record)
    linked = tmp_path / "another-name.db"
    os.link(record, linked)
    (tmp_path / "sub").mkdir()
    assert reconstruct_prompts.is_the_live_record(record)
    assert reconstruct_prompts.is_the_live_record(linked), "a hard link walked past"
    assert reconstruct_prompts.is_the_live_record(tmp_path / "sub" / ".." / "record.db")
    copy = tmp_path / "copy.db"
    db.back_up(record, copy, "a copy of a scratch record, which is not the record")
    assert not reconstruct_prompts.is_the_live_record(copy)
    with pytest.raises(SystemExit) as refused:
        reconstruct_prompts.reconstruct(linked)
    assert refused.value.code == 2
    with pytest.raises(SystemExit):
        reconstruct_prompts.reconstruct(copy, live=True)
    with pytest.raises(SystemExit):
        # a copy that was never opened under the schema has no instant
        reconstruct_prompts.reconstruct(copy)


def test_commit_at_reads_the_latest_move_at_or_before_the_minute():
    def at(stamp):
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    entries = [reconstruct_prompts.ReflogEntry(at("2026-09-02T05:44:27Z"), "a" * 40, "x"),
               reconstruct_prompts.ReflogEntry(at("2026-09-05T02:22:43Z"), "b" * 40, "y")]
    assert reconstruct_prompts.commit_at(entries, "2026-09-01T00:00:00Z") is None
    assert reconstruct_prompts.commit_at(entries, "2026-09-02T05:44:27Z").commit == "a" * 40
    assert reconstruct_prompts.commit_at(entries, "2026-09-05T02:22:42Z").commit == "a" * 40
    assert reconstruct_prompts.commit_at(entries, "2026-09-25T00:00:00Z").commit == "b" * 40


# ---------------------------------------------------------------------------
# the words on the page
# ---------------------------------------------------------------------------

def test_the_labels_say_what_each_record_is():
    assert language.prompt_label("reconstructed") == "The prompt, reconstructed"
    assert "reconstructed" in language.prompt_label("reconstructed")
    assert "reconstructed" not in language.prompt_label("sent").lower()
    for kind in ("sent", "reconstructed", None):
        for text in (language.prompt_label(kind),
                     language.prompt_note(kind, "2026-09-25T20:00:00Z",
                                          "Built by the code of the time.")):
            assert audit.plain_words_violations(text) == [], text
            assert audit.advice_word_faults(text) == [], text
            assert audit.pressure_word_faults(text) == [], text
    note = language.prompt_note("reconstructed", "2026-09-25T20:00:00Z")
    assert "Friday 25 September" in note and "not it" in note
    # EVERY PART OF A RECONSTRUCTION SAYS SO BESIDE ITS TEXT (render check,
    # 2026-09-25), and no part of a sent prompt does.
    for part in language.PROMPT_PART_LABELS:
        rebuilt = language.prompt_part_label(part, "reconstructed")
        sent = language.prompt_part_label(part, "sent")
        assert rebuilt.endswith(", reconstructed"), rebuilt
        assert "reconstructed" not in sent.lower(), sent
        for text in (rebuilt, sent):
            assert audit.plain_words_violations(text) == [], text


def test_the_page_carries_the_prompt_by_the_records_own_kind(trained, db_path):
    client = StubClient([ANSWER] * 40)
    run.run_week(trained, 2025, 7, include_props=False, use_llm=True,
                 llm_client=client)
    old = _old_reasoning_rows(trained, n=1)[0]
    entry = reconstruct_prompts.ReflogEntry(
        datetime(2025, 1, 1, tzinfo=timezone.utc), _head(), "planted history")
    reconstruct_prompts.reconstruct(db_path, entries=[entry])
    history = views.history(trained, sport="nfl", predictor="llm")
    kinds = {i["prediction_id"]: i["prompt"]["kind"] for i in history["items"]}
    assert kinds[old] == "reconstructed"
    assert sorted(set(kinds.values())) == ["reconstructed", "sent"]
    assert audit.prompt_label_faults(trained, [history]) == []
    statistical = views.history(trained, sport="nfl", predictor="statistical")
    assert all(i["prompt"] is None for i in statistical["items"])

    detail = views.prompt_detail(trained, old)
    record = prompt_record.record_for(trained, old)
    request = json.loads(record["request_json"])
    assert detail["label"] == "The prompt, reconstructed"
    assert [p["text"] for p in detail["parts"]] == [
        request["system"], request["messages"][0]["content"]]
    assert detail["code_version"] == record["code_version"]
    assert all("reconstructed" in p["label"] for p in detail["parts"]), detail["parts"]
    sent_id = next(pid for pid, k in kinds.items() if k == "sent")
    sent = views.prompt_detail(trained, sent_id)
    assert sent["label"] == "The prompt it was sent" and sent["code_version"] is None
    assert not [p for p in sent["parts"] if "reconstructed" in p["label"].lower()]
    stat_id = statistical["items"][0]["prediction_id"]
    assert views.prompt_detail(trained, stat_id) is None


def test_the_register_holds_only_the_eight_behavioural_differences():
    """The ninth entry, `spread_sign_source`, was cleared by 5a's release and
    removed by the next commit, as the register's own rule requires."""
    register = audit.SCHEMA_DIFFERENCES_REGISTERED
    assert len(register) == 8
    assert not [e for e in register if "spread_sign_source" in e.property]
    assert all(e.comparisons == ("release", "tree") for e in register)


def test_the_prompt_record_has_one_door():
    assert audit.prompt_record_door_faults() == []
