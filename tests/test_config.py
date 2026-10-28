"""The local .env loader (app/config.py): a copy of .env.example must load as the README says."""
import os
import re

from app import config

EXAMPLE = config.ROOT / ".env.example"
NAMES = re.findall(r"^#?\s*([A-Z_]+)=", EXAMPLE.read_text(encoding="utf-8"), re.M)


def _clean_env(monkeypatch, names):
    # setenv first so monkeypatch records the original state and restores it after the test,
    # including removing variables the loader adds.
    for name in names:
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)


def test_copied_env_example_loads(monkeypatch):
    _clean_env(monkeypatch, NAMES)
    config._load_dotenv(EXAMPLE)
    s = config.load_settings()
    assert s.environment == "local"
    assert s.app_password == "change-me"
    assert s.database_url == "sqlite:///./local.db"
    assert s.history_limit == 20
    assert s.daily_cap_usd == 3.0
    assert s.anthropic_api_key is None  # the line holds only a comment


def test_quoted_value_keeps_its_hash(tmp_path, monkeypatch):
    _clean_env(monkeypatch, ["APP_PASSWORD", "TIMEZONE", "MODEL"])
    env = tmp_path / ".env"
    env.write_text('APP_PASSWORD="pa ss#word"   # team password\n'
                   "MODEL='claude-opus-5-5'\n"
                   "TIMEZONE=Asia/Jerusalem#not-a-comment\n", encoding="utf-8")
    config._load_dotenv(env)
    assert os.environ["APP_PASSWORD"] == "pa ss#word"
    assert os.environ["MODEL"] == "claude-opus-5-5"
    assert os.environ["TIMEZONE"] == "Asia/Jerusalem#not-a-comment"
