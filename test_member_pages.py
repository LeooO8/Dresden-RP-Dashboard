"""Tests für die Bewohner-Funktionen im Dashboard: Bank (Modul-Schalter), Shop-Kauf, Giveaway-Teilnahme, Buchungen,
Mitgliedersuche und die Mitgliederliste fürs Team. Ausführen: pytest -v tests/test_member_pages.py"""
import os, tempfile
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_db.name}"

import pytest  # noqa: E402

pytest.importorskip("jwt")
pytest.importorskip("PIL")

import app as botapp  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from database import SessionLocal, init_db, engine  # noqa: E402
from models import Base, Giveaway, LogEntry, Setting, ShopItem, Transaction, User  # noqa: E402
from helpers import AuthEnv  # noqa: E402

G1, G2 = "1", "2"
ENV = None


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    global ENV
    Base.metadata.drop_all(bind=engine); init_db()
    monkeypatch.setattr(botapp, "OWNER_DISCORD_IDS", set()); monkeypatch.setattr(botapp, "OWNER_BOOTSTRAP_IDS", set())
    ENV = AuthEnv(botapp, monkeypatch)
    yield


def me(role="Mitglied", balance=1000, cash=0, guild=G1):
    ENV.set_role(guild, role)
    with SessionLocal() as db:
        u = db.get(User, f"{guild}:42"); u.balance, u.cash = balance, cash; db.commit()
    return ENV.client()


def user_row(did, guild=G1, balance=0, name=None):
    with SessionLocal() as db:
        db.add(User(id=f"{guild}:{did}", guild_id=guild, discord_id=did, username=name or f"u{did}", balance=balance, cash=0)); db.commit()


def get_user(did="42", guild=G1):
    with SessionLocal() as db:
        u = db.get(User, f"{guild}:{did}"); return u.balance, u.cash


def add_item(name="Handy", price=300, guild=G1, role_id=None):
    with SessionLocal() as db:
        it = ShopItem(guild_id=guild, name=name, category="Technik", price=price, sold=0, role_id=role_id); db.add(it); db.commit(); return it.id


def sold(item_id):
    with SessionLocal() as db:
        return db.get(ShopItem, item_id).sold


def disable(module, guild=G1):
    with SessionLocal() as db:
        db.add(Setting(key=f"{guild}:modul_{module}", value="nein")); db.commit()


# ------------------------------------------------------------------ Shop
def test_kauf_bucht_ab_zaehlt_verkauf_und_protokolliert():
    c = me(balance=1000); iid = add_item(price=300)
    r = c.post(f"/api/shop/items/{iid}/buy?guild_id={G1}")
    assert r.status_code == 200 and r.json()["balance"] == 700 and r.json()["item"] == "Handy" and r.json()["role"] is None
    assert get_user()[0] == 700 and sold(iid) == 1
    with SessionLocal() as db:
        t = db.query(Transaction).one()
        assert (t.type, t.amount, t.from_user, t.to_user) == ("Kauf", 300, "tester", "Shop")
        assert any("kaufte 'Handy'" in l.text for l in db.query(LogEntry).all())


def test_kauf_ohne_genug_guthaben_aendert_nichts():
    c = me(balance=299); iid = add_item(price=300)
    r = c.post(f"/api/shop/items/{iid}/buy?guild_id={G1}")
    assert r.status_code == 400 and "Nicht genug Guthaben" in r.json()["detail"]
    assert get_user()[0] == 299 and sold(iid) == 0
    with SessionLocal() as db:
        assert db.query(Transaction).count() == 0


def test_kauf_mit_genau_dem_guthaben_klappt_zweiter_kauf_nicht():
    c = me(balance=300); iid = add_item(price=300)
    assert c.post(f"/api/shop/items/{iid}/buy?guild_id={G1}").status_code == 200
    assert c.post(f"/api/shop/items/{iid}/buy?guild_id={G1}").status_code == 400
    assert get_user()[0] == 0 and sold(iid) == 1


def test_kauf_artikel_anderer_server_oder_unbekannt_ist_404():
    c = me(balance=1000); other = add_item(guild=G2); 
    assert c.post(f"/api/shop/items/{other}/buy?guild_id={G1}").status_code == 404
    assert c.post(f"/api/shop/items/9999/buy?guild_id={G1}").status_code == 404
    assert get_user()[0] == 1000


def test_kauf_modul_shop_ausgeschaltet():
    c = me(balance=1000); iid = add_item(); disable("shop")
    r = c.post(f"/api/shop/items/{iid}/buy?guild_id={G1}")
    assert r.status_code == 403 and "ausgeschaltet" in r.json()["detail"] and get_user()[0] == 1000


def test_kauf_vergibt_rolle_oder_meldet_fehlschlag(monkeypatch):
    c = me(balance=1000); iid = add_item(role_id="555")
    member = SimpleNamespace(id=42, display_name="tester", bot=False, name="tester", roles=[], add_roles=AsyncMock())
    role = SimpleNamespace(id=555)
    base = ENV._get_guild(G1)
    guild = SimpleNamespace(**{**base.__dict__, "get_member": lambda uid: member if uid == 42 else None, "get_role": lambda rid: role if rid == 555 else None})
    monkeypatch.setattr(botapp.bot, "get_guild", lambda gid: guild)
    r = c.post(f"/api/shop/items/{iid}/buy?guild_id={G1}")
    assert r.json()["role"] == "vergeben" and member.add_roles.await_count == 1
    guild2 = SimpleNamespace(**{**base.__dict__, "get_member": lambda uid: member, "get_role": lambda rid: None})
    monkeypatch.setattr(botapp.bot, "get_guild", lambda gid: guild2)
    r = c.post(f"/api/shop/items/{iid}/buy?guild_id={G1}")
    assert r.status_code == 200 and r.json()["role"] == "fehlgeschlagen"           # Geld ist weg, Hinweis kommt (wie im Discord)


def test_kauf_nur_angemeldet():
    iid = add_item()
    assert TestClient(botapp.app).post(f"/api/shop/items/{iid}/buy?guild_id={G1}").status_code == 401


# ------------------------------------------------------------------ Giveaways
def add_giveaway(guild=G1, status="aktiv", minutes=60, participants=""):
    with SessionLocal() as db:
        g = Giveaway(guild_id=guild, prize="Auto", status=status, ends_at=datetime.now(timezone.utc) + timedelta(minutes=minutes), participants=participants, entries=len([p for p in participants.split(",") if p]))
        db.add(g); db.commit(); return g.id


def participants(gid):
    with SessionLocal() as db:
        g = db.get(Giveaway, gid); return g.participants, g.entries


def test_teilnahme_und_austritt():
    c = me(); gid = add_giveaway(participants="7")
    r = c.post(f"/api/giveaways/{gid}/join?guild_id={G1}")
    assert r.status_code == 200 and r.json() == {"ok": True, "joined": True, "entries": 2}
    assert participants(gid) == ("7,42", 2)
    assert c.post(f"/api/giveaways/{gid}/join?guild_id={G1}").json()["entries"] == 2          # doppelt zählt nicht
    assert participants(gid) == ("7,42", 2)
    r = c.post(f"/api/giveaways/{gid}/leave?guild_id={G1}")
    assert r.json() == {"ok": True, "joined": False, "entries": 1} and participants(gid) == ("7", 1)
    assert c.post(f"/api/giveaways/{gid}/leave?guild_id={G1}").json()["entries"] == 1


def test_teilnahme_beendet_abgelaufen_fremd_und_modul():
    c = me()
    ended = add_giveaway(status="beendet"); expired = add_giveaway(minutes=-5); foreign = add_giveaway(guild=G2)
    assert c.post(f"/api/giveaways/{ended}/join?guild_id={G1}").status_code == 400
    assert c.post(f"/api/giveaways/{expired}/join?guild_id={G1}").status_code == 400
    assert c.post(f"/api/giveaways/{foreign}/join?guild_id={G1}").status_code == 404
    assert participants(foreign) == ("", 0)
    ok = add_giveaway(); disable("giveaways")
    assert c.post(f"/api/giveaways/{ok}/join?guild_id={G1}").status_code == 403


def test_me_giveaways_zeigt_meine_teilnahme():
    c = me(); a = add_giveaway(participants="42,7"); b = add_giveaway(participants="7")
    rows = {r["id"]: r for r in c.get(f"/api/me/giveaways?guild_id={G1}").json()}
    assert rows[a]["joined"] is True and rows[b]["joined"] is False and rows[a]["entries"] == 2
    add_giveaway(guild=G2)
    assert len(c.get(f"/api/me/giveaways?guild_id={G1}").json()) == 2                           # nur der eigene Server


# ------------------------------------------------------------------ Bank
def test_bank_modul_ausgeschaltet_sperrt_ueberweisen_einzahlen_abheben():
    c = me(balance=500, cash=500); user_row("7", balance=0); disable("bank")
    assert c.post(f"/api/bank/deposit?guild_id={G1}&betrag=10").status_code == 403
    assert c.post(f"/api/bank/withdraw?guild_id={G1}&betrag=10").status_code == 403
    assert c.post(f"/api/bank/transfer?guild_id={G1}&empfaenger_id={G1}:7&betrag=10").status_code == 403
    assert get_user() == (500, 500)


def test_bank_funktioniert_mit_modul_an():
    c = me(balance=500, cash=100); user_row("7")
    assert c.post(f"/api/bank/deposit?guild_id={G1}&betrag=100").json()["balance"] == 600
    assert c.post(f"/api/bank/withdraw?guild_id={G1}&betrag=50").json()["cash"] == 50
    assert c.post(f"/api/bank/transfer?guild_id={G1}&empfaenger_id={G1}:7&betrag=100").status_code == 200
    assert get_user("7")[0] == 100 and get_user()[0] == 450


def test_ueberweisung_auf_konto_eines_anderen_servers_ist_gesperrt():
    c = me(balance=500); user_row("77", guild=G2, balance=0)
    r = c.post(f"/api/bank/transfer?guild_id={G1}&empfaenger_id={G2}:77&betrag=100")
    assert r.status_code == 404 and get_user()[0] == 500 and get_user("77", G2)[0] == 0


def test_ueberweisung_validierung():
    c = me(balance=50); user_row("7")
    assert c.post(f"/api/bank/transfer?guild_id={G1}&empfaenger_id={G1}:7&betrag=100").status_code == 400    # zu wenig
    assert c.post(f"/api/bank/transfer?guild_id={G1}&empfaenger_id={G1}:7&betrag=-5").status_code == 400     # negativ
    assert c.post(f"/api/bank/transfer?guild_id={G1}&empfaenger_id={G1}:42&betrag=10").status_code == 400     # an sich selbst
    assert get_user()[0] == 50


# ------------------------------------------------------------------ Buchungen
def test_me_transactions_nur_eigene_neueste_zuerst():
    c = me()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        db.add_all([Transaction(guild_id=G1, from_user="tester", to_user="Max", amount=1, type="Überweisung", created_at=now - timedelta(minutes=5)),
                    Transaction(guild_id=G1, from_user="Zinsen", to_user="tester", amount=2, type="Zinsen", created_at=now),
                    Transaction(guild_id=G1, from_user="Anna", to_user="Max", amount=3, type="Überweisung"),
                    Transaction(guild_id=G2, from_user="tester", to_user="Max", amount=4, type="Überweisung")]); db.commit()
    rows = c.get(f"/api/me/transactions?guild_id={G1}").json()
    assert [r["amount"] for r in rows] == [2, 1]


# ------------------------------------------------------------------ Mitgliedersuche und Mitgliederliste
def test_mitgliedersuche_ab_zwei_zeichen_ohne_mich_und_bots():
    c = me()
    ENV.extra_members = {7: SimpleNamespace(id=7, display_name="Anna Beispiel", name="anna", bot=False, roles=[]),
                         8: SimpleNamespace(id=8, display_name="Annabot", name="annabot", bot=True, roles=[]),
                         9: SimpleNamespace(id=9, display_name="Ben", name="ben", bot=False, roles=[])}
    assert c.get(f"/api/members/search?guild_id={G1}&q=a").json() == []                         # zu kurz
    assert c.get(f"/api/members/search?guild_id={G1}&q=an").json() == [{"id": f"{G1}:7", "name": "Anna Beispiel"}]
    assert c.get(f"/api/members/search?guild_id={G1}&q=tester").json() == []                    # nicht der Suchende selbst


def test_mitgliederliste_fuers_team_ohne_geld_und_users_nur_fuer_admins():
    ENV.set_role(G1, "Support"); c = ENV.client()
    ENV.extra_members = {7: SimpleNamespace(id=7, display_name="Anna", name="anna", bot=False, roles=[], joined_at=datetime.now(timezone.utc))}
    rows = c.get(f"/api/members?guild_id={G1}").json()
    assert rows and all("balance" not in r and "cash" not in r for r in rows) and {"id", "name", "role"} <= set(rows[0])
    assert c.get(f"/api/users?guild_id={G1}").status_code == 403                                 # Kontostände nur für Admins
    ENV.set_role(G1, "Admin")
    assert "balance" in ENV.client().get(f"/api/users?guild_id={G1}").json()[0]


def test_mitgliederliste_nicht_fuer_bewohner():
    me()
    assert ENV.client().get(f"/api/members?guild_id={G1}").status_code == 403


# ------------------------------------------------------------------ Einladungslink
def test_einladungslink_nur_wenn_gueltig(monkeypatch):
    monkeypatch.setattr(botapp, "BOT_INVITE_URL", "https://discord.com/oauth2/authorize?client_id=1&scope=bot")
    assert TestClient(botapp.app).get("/api/public-status").json()["invite_url"].startswith("https://discord.com/")
    monkeypatch.setattr(botapp, "BOT_INVITE_URL", "")
    assert TestClient(botapp.app).get("/api/public-status").json()["invite_url"] is None
