"""Tests für die Anmeldeseite/Serverauswahl: GET /api/public-status und GET /api/my-guilds.
Ausführen: pytest -v tests/test_login_server.py"""
import os, tempfile
from types import SimpleNamespace

_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_db.name}"

import pytest  # noqa: E402

pytest.importorskip("jwt")
pytest.importorskip("PIL")

import app as botapp  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from database import SessionLocal, init_db, engine  # noqa: E402
from models import Base, User  # noqa: E402
from helpers import AuthEnv  # noqa: E402


ENV = None


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    global ENV
    Base.metadata.drop_all(bind=engine); init_db()
    ENV = AuthEnv(botapp, monkeypatch)
    yield


def fake_guild(gid, name, members, roles=5, icon=None):
    return SimpleNamespace(id=gid, name=name, icon=SimpleNamespace(url=icon) if icon else None, member_count=len(members) + 20,
                           roles=[SimpleNamespace(name="@everyone")] + [SimpleNamespace(name=f"r{i}") for i in range(roles)],
                           get_member=lambda uid: object() if uid in members else None)


def test_public_status_ohne_login_und_ohne_interne_daten():
    r = TestClient(botapp.app).get("/api/public-status")
    assert r.status_code == 200
    assert set(r.json()) == {"bot_status", "uptime_seconds", "invite_url"}          # keine Servernamen, Mitglieder- oder Guthabenzahlen
    assert r.json()["bot_status"] in ("online", "offline") and r.json()["uptime_seconds"] >= 0


def test_my_guilds_nur_eigene_server_mit_zahlen_und_rolle(monkeypatch):
    guilds = [fake_guild(1, "Dresden RP", {42}, roles=152, icon="https://cdn/x.png"), fake_guild(2, "Fremd", {99})]
    monkeypatch.setattr(type(botapp.bot), "guilds", property(lambda self: guilds))
    with SessionLocal() as db:
        db.add(User(id="1:42", guild_id="1", discord_id="42", username="tester", role="Support")); db.commit()
    r = ENV.client().get("/api/my-guilds")
    assert r.status_code == 200
    assert r.json() == [{"id": "1", "name": "Dresden RP", "icon_url": "https://cdn/x.png",
                         "member_count": 21, "role_count": 152, "my_role": "Support"}]   # @everyone nicht mitgezählt, Server 2 fehlt


def test_my_guilds_ohne_datenbankeintrag_ist_bewohner(monkeypatch):
    monkeypatch.setattr(type(botapp.bot), "guilds", property(lambda self: [fake_guild(1, "Dresden RP", {42})]))
    item = ENV.client().get("/api/my-guilds").json()[0]
    assert item["my_role"] == "Mitglied" and item["icon_url"] is None


def test_my_guilds_verlangt_login():
    assert TestClient(botapp.app).get("/api/my-guilds").status_code == 401


# ------------------------------------------------------------------ Optionales HTTPS (SSL_CERTFILE / SSL_KEYFILE)
def test_tls_ohne_angaben_bleibt_unverschluesselt(monkeypatch):
    monkeypatch.delenv("SSL_CERTFILE", raising=False); monkeypatch.delenv("SSL_KEYFILE", raising=False)
    assert botapp.tls_options() == {}


def test_tls_mit_vorhandenen_dateien(monkeypatch, tmp_path, capsys):
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("x"); key.write_text("y")
    monkeypatch.setenv("SSL_CERTFILE", str(cert)); monkeypatch.setenv("SSL_KEYFILE", str(key))
    assert botapp.tls_options() == {"ssl_certfile": str(cert), "ssl_keyfile": str(key)}
    assert "HTTPS aktiv" in capsys.readouterr().out


def test_tls_unvollstaendig_oder_datei_fehlt_startet_ohne_https_mit_warnung(monkeypatch, tmp_path, capsys):
    cert = tmp_path / "c.pem"; cert.write_text("x")
    monkeypatch.setenv("SSL_CERTFILE", str(cert)); monkeypatch.delenv("SSL_KEYFILE", raising=False)
    assert botapp.tls_options() == {}
    monkeypatch.setenv("SSL_KEYFILE", str(tmp_path / "gibt-es-nicht.pem"))
    assert botapp.tls_options() == {}
    assert "OHNE HTTPS" in capsys.readouterr().out
