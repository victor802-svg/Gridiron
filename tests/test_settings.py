"""`.env` holds the installation's settings, and holds them for real.

THE DEFECT THIS CLOSES was a trap rather than a missing feature. The file has
always existed and has always carried the access token, but it was read by a
parser that looked for exactly one name and ignored every other line. Adding
`ANTHROPIC_API_KEY=` to it would have produced a file that looked entirely
correct and was read by nobody -- which is worse than the failure it was meant
to fix, because it looks fixed.
"""

from __future__ import annotations

import os

import pytest

from gridiron import config


def test_a_setting_file_is_read_whole(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "# a comment\n"
        "\n"
        "GRIDIRON_ACCESS_TOKEN=abc123\n"
        "ANTHROPIC_API_KEY=sk-ant-example\n",
        encoding="utf-8")
    values = config.read_env_file(path)
    assert values == {"GRIDIRON_ACCESS_TOKEN": "abc123",
                      "ANTHROPIC_API_KEY": "sk-ant-example"}


def test_quotes_and_whitespace_are_stripped(tmp_path):
    path = tmp_path / ".env"
    path.write_text('KEY = "spaced"\nOTHER=\'single\'\n', encoding="utf-8")
    values = config.read_env_file(path)
    assert values["KEY"] == "spaced"
    assert values["OTHER"] == "single"


def test_a_missing_file_is_not_an_error(tmp_path):
    """Running from a checkout with no `.env` is the ordinary case."""
    assert config.read_env_file(tmp_path / "nothing-here") == {}


def test_a_line_that_is_not_a_setting_is_ignored(tmp_path):
    path = tmp_path / ".env"
    path.write_text("just some words\n# KEY=commented\nREAL=yes\n", encoding="utf-8")
    assert config.read_env_file(path) == {"REAL": "yes"}


def test_the_process_environment_wins(monkeypatch, tmp_path):
    """A variable set for one run overrides the file without editing it.

    The reverse would let a stale file silently beat an explicit instruction,
    which is the wrong way round for the case that matters: trying a different
    key, or pointing one run at a different database.
    """
    monkeypatch.setattr(config, "_FILE_SETTINGS", {"THING": "from-file"})
    monkeypatch.delenv("THING", raising=False)
    assert config.setting("THING") == "from-file"
    monkeypatch.setenv("THING", "from-environment")
    assert config.setting("THING") == "from-environment"


def test_a_setting_absent_everywhere_is_the_default(monkeypatch):
    monkeypatch.setattr(config, "_FILE_SETTINGS", {})
    monkeypatch.delenv("NOT_SET_ANYWHERE", raising=False)
    assert config.setting("NOT_SET_ANYWHERE") == ""
    assert config.setting("NOT_SET_ANYWHERE", "fallback") == "fallback"


def test_the_token_still_comes_from_the_same_file(tmp_path, monkeypatch):
    """The regression that matters: one parser now serves both, and the
    access token must keep working exactly as it did."""
    from gridiron import auth

    path = tmp_path / ".env"
    path.write_text("GRIDIRON_ACCESS_TOKEN=tok-from-file\n", encoding="utf-8")
    monkeypatch.setattr(auth, "ENV_FILE", path)
    monkeypatch.delenv(auth.TOKEN_VAR, raising=False)
    assert auth.read_token() == "tok-from-file"
    # And the environment still wins for it too.
    monkeypatch.setenv(auth.TOKEN_VAR, "tok-from-env")
    assert auth.read_token() == "tok-from-env"


def test_a_rotated_token_is_seen_without_a_restart(tmp_path, monkeypatch):
    """The token is re-read rather than cached at import: rotating it while
    the server runs should take effect on the next request."""
    from gridiron import auth

    path = tmp_path / ".env"
    monkeypatch.setattr(auth, "ENV_FILE", path)
    monkeypatch.delenv(auth.TOKEN_VAR, raising=False)
    path.write_text("GRIDIRON_ACCESS_TOKEN=first\n", encoding="utf-8")
    assert auth.read_token() == "first"
    path.write_text("GRIDIRON_ACCESS_TOKEN=second\n", encoding="utf-8")
    assert auth.read_token() == "second"


def test_the_api_key_is_reachable_from_the_settings_file(monkeypatch):
    """The whole point of the change, asserted on the real name."""
    monkeypatch.setattr(config, "_FILE_SETTINGS",
                        {"ANTHROPIC_API_KEY": "sk-ant-from-file"})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert config.setting("ANTHROPIC_API_KEY") == "sk-ant-from-file"


def test_no_setting_value_is_ever_logged():
    """A settings reader that prints is a settings reader that leaks.

    Crude on purpose: the function's source must contain no print or logging
    call at all. There is no safe amount of logging a secret.
    """
    import inspect

    source = inspect.getsource(config.read_env_file)
    for leak in ("print(", "logging", "logger", "warn("):
        assert leak not in source, f"read_env_file contains {leak!r}"
