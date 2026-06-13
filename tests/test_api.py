from fc26.api.app import create_app
from pathlib import Path


def test_create_app_returns_fastapi(tmp_path):
    from fastapi import FastAPI
    squads_dir = tmp_path / "squads"
    squads_dir.mkdir()
    db = tmp_path / "players.json"
    db.write_text('{"schema_version": 1, "cards": []}')
    app = create_app(db, squads_dir)
    assert isinstance(app, FastAPI)
