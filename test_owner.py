"""Tests für die Inhaber-Rolle (Owner): feste Inhaber über OWNER_DISCORD_IDS, ernannte Inhaber, Rollenvergabe und Absicherung.
Ausführen: pytest -v tests/test_owner.py"""
import os, tempfile
from types import SimpleNamespace

_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_db.name}"

import pytest  # noqa: E402

pytest.importorskip("jwt")
pytest.importorskip("PIL")

import app as botapp  # noqa: E402
import permissions  # noqa: E402
from fastapi import Depends, FastAPI  # noqa: E402
from database import SessionLocal, init_db, engine  # noqa: E402
from models import Base, Setting, User  # noqa: E402
from helpers import AuthEnv  # noqa: E402

G1 = "1"
ENV = None


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    global ENV
    Base.metadata.drop_all(bind=engine); init_db()
    monkeypatch.setattr(botapp, "OWNER_DISCORD_IDS", set())
    monkeypatch.setattr(botapp, "OWNER_BOOTSTRAP_IDS", set())
    ENV = AuthEnv(botapp, monkeypatch)
    yield


def add_user(did, role):
    with SessionLocal() as db:
        db.add(User(id=f"{G1}:{did}", guild_id=G1, discord_id=did, username=f"u{did}", role=role)); db.commit()


def role_of(did):
    with SessionLocal() as db:
        return db.get(User, f"{G1}:{did}").role


def setting(key):
    with SessionLocal() as db:
        s = db.get(Setting, f"{G1}:{key}")
        return s.value if s else None


def role_call(c, did, role):
    return c.post(f"/api/users/{G1}:{did}/role?guild_id={G1}&role={role}")


def fake_guild(member_id, owner_id=999, role_ids=()):
    member = SimpleNamespace(id=member_id, roles=[SimpleNamespace(id=r) for r in role_ids])
    return SimpleNamespace(id=int(G1), owner_id=owner_id, get_member=lambda uid: member if uid == member_id else None)


def sync(did, guild):
    with SessionLocal() as db:
        u = db.get(User, f"{G1}:{did}")
        botapp.sync_admin_role(db, guild, u)
        db.commit()
    return role_of(did)


# ------------------------------------------------------------------ Umgebungsvariable
def test_owner_ids_werden_eingelesen_und_ungueltiges_ignoriert():
    ids, invalid = botapp._parse_discord_ids("123456789012345678, 234567890123456789;abc 12 \n345678901234567890")
    assert ids == {"123456789012345678", "234567890123456789", "345678901234567890"} and invalid == ["abc", "12"]
    assert botapp._parse_discord_ids("") == (set(), [])
    assert botapp._parse_discord_ids(None) == (set(), [])


# ------------------------------------------------------------------ Rollen-Abgleich (sync_admin_role)
def test_discord_serverbesitzer_bleibt_automatisch_owner():
    add_user("500", "Mitglied")
    assert sync("500", fake_guild(500, owner_id=500)) == "Owner"


def test_eingetragener_inhaber_wird_owner_auch_mit_admin_rolle(monkeypatch):
    monkeypatch.setattr(botapp, "OWNER_DISCORD_IDS", {"500"})
    with SessionLocal() as db:
        db.add(Setting(key=f"{G1}:admin_rolle", value="777")); db.commit()
    add_user("500", "Mitglied")
    assert sync("500", fake_guild(500, role_ids=[777])) == "Owner"          # wird nicht zu Admin abgestuft
    assert sync("500", fake_guild(500)) == "Owner"


def test_ausgetragener_inhaber_wird_abgestuft(monkeypatch):
    monkeypatch.setattr(botapp, "OWNER_DISCORD_IDS", {"500"})
    add_user("500", "Mitglied"); assert sync("500", fake_guild(500)) == "Owner"
    monkeypatch.setattr(botapp, "OWNER_DISCORD_IDS", set())                  # aus der Umgebungsvariable entfernt
    assert sync("500", fake_guild(500)) == "Mitglied"
    with SessionLocal() as db:
        db.add(Setting(key=f"{G1}:admin_rolle", value="777")); db.commit()
    with SessionLocal() as db:
        db.get(User, f"{G1}:500").role = "Owner"; db.commit()
    assert sync("500", fake_guild(500, role_ids=[777])) == "Admin"           # mit Admin-Rolle landet er bei Admin


def test_ernannter_inhaber_bleibt_owner_bis_er_abgestuft_wird():
    add_user("600", "Owner")
    with SessionLocal() as db:
        botapp.set_appointed_owner(db, G1, "600", True); db.commit()
    assert sync("600", fake_guild(600)) == "Owner"
    with SessionLocal() as db:
        botapp.set_appointed_owner(db, G1, "600", False); db.commit()
    assert sync("600", fake_guild(600)) == "Mitglied"


def test_normaler_admin_wird_nicht_zum_owner():
    with SessionLocal() as db:
        db.add(Setting(key=f"{G1}:admin_rolle", value="777")); db.commit()
    add_user("700", "Mitglied")
    assert sync("700", fake_guild(700, role_ids=[777])) == "Admin"


def test_ohne_erreichbaren_server_wird_nichts_entzogen():
    add_user("500", "Owner")
    assert sync("500", None) == "Owner"                                       # Bot offline / Server nicht im Cache
    assert sync("500", fake_guild(123)) == "Owner"                            # Mitglied (noch) nicht im Cache


# ------------------------------------------------------------------ Voller Zugriff für den Inhaber
def sweep_app():
    app = FastAPI(dependencies=[Depends(botapp.enforce_permissions)])
    for (method, path) in permissions.PERMISSIONS:
        app.add_api_route(path, lambda: {"ok": True}, methods=[method])
    return app


def test_eingetragener_inhaber_hat_vollzugriff_auf_alle_endpunkte(monkeypatch):
    monkeypatch.setattr(botapp, "OWNER_DISCORD_IDS", {"42"})
    ENV.set_role(G1, "Mitglied")                                              # in der Datenbank steht noch Mitglied
    me = ENV.client().get(f"/api/my-role?guild_id={G1}")
    assert me.status_code == 200 and me.json()["role"] == "Owner"
    c = ENV.client(sweep_app())
    denied = [(m, p) for (m, p) in permissions.PERMISSIONS if c.request(m, f"{p}?guild_id={G1}").status_code != 200]
    assert denied == []


def test_inhaber_aus_umgebungsvariable_gilt_pro_server_nur_als_mitglied(monkeypatch):
    monkeypatch.setattr(botapp, "OWNER_DISCORD_IDS", {"42"})
    ENV.guilds = {"1"}                                                         # auf Server 2 ist der Nutzer kein Mitglied
    c = ENV.client()
    assert c.get("/api/my-role?guild_id=1").json()["role"] == "Owner"
    assert c.get("/api/my-role?guild_id=2").status_code == 403


def test_nicht_eingetragener_nutzer_bleibt_normal():
    ENV.set_role(G1, "Mitglied")
    assert ENV.client().get(f"/api/my-role?guild_id={G1}").json()["role"] == "Mitglied"


# ------------------------------------------------------------------ Einstellungen
def test_admin_rolle_nur_fuer_inhaber():
    ENV.set_role(G1, "Admin"); c = ENV.client()
    assert c.post(f"/api/settings?guild_id={G1}", json={"admin_rolle": "777"}).status_code == 403
    assert c.post(f"/api/settings?guild_id={G1}", json={"startguthaben": "800"}).status_code == 200      # andere Einstellungen gehen weiter
    ENV.set_role(G1, "Owner")
    assert ENV.client().post(f"/api/settings?guild_id={G1}", json={"admin_rolle": "777"}).status_code == 200
    assert setting("admin_rolle") == "777"


def test_inhaber_liste_nicht_ueber_einstellungen_aenderbar():
    ENV.set_role(G1, "Owner"); c = ENV.client()
    r = c.post(f"/api/settings?guild_id={G1}", json={"owner_ernannt": "42,43"})
    assert r.status_code == 400 and setting("owner_ernannt") is None


# ------------------------------------------------------------------ Rollenvergabe
def test_admin_kann_niemanden_zum_owner_machen_auch_sich_selbst_nicht():
    ENV.set_role(G1, "Admin"); add_user("99", "Mitglied"); c = ENV.client()
    assert role_call(c, "99", "Owner").status_code == 403 and role_of("99") == "Mitglied"
    assert role_call(c, "42", "Owner").status_code == 403 and role_of("42") == "Admin"       # nicht selbst befördern
    assert setting("owner_ernannt") is None


def test_admin_kann_keinen_owner_veraendern():
    ENV.set_role(G1, "Admin"); add_user("99", "Owner"); c = ENV.client()
    assert role_call(c, "99", "Mitglied").status_code == 403 and role_of("99") == "Owner"


@pytest.mark.parametrize("role", ["Mitglied", "Support", "Moderator"])
def test_niedrigere_rollen_koennen_keine_rechte_vergeben(role):
    ENV.set_role(G1, role); c = ENV.client()
    for new_role in ("Owner", "Admin", "Support"):
        assert role_call(c, "42", new_role).status_code == 403
        assert role_call(c, "99", new_role).status_code == 403
    assert role_of("42") == role and setting("owner_ernannt") is None


def test_inhaber_ernennt_weiteren_inhaber_und_entzieht_ihm_die_rechte_wieder():
    ENV.set_role(G1, "Owner"); add_user("99", "Mitglied"); c = ENV.client()
    assert role_call(c, "99", "Owner").status_code == 200
    assert role_of("99") == "Owner" and setting("owner_ernannt") == "99"
    assert sync("99", fake_guild(99)) == "Owner"                              # bleibt nach dem Rollen-Abgleich Inhaber
    assert role_call(c, "99", "Mitglied").status_code == 200
    assert role_of("99") == "Mitglied" and setting("owner_ernannt") == ""
    assert sync("99", fake_guild(99)) == "Mitglied"


def test_niemand_aendert_die_eigene_inhaberrolle():
    ENV.set_role(G1, "Owner"); c = ENV.client()
    for new_role in ("Mitglied", "Admin", "Moderator", "Owner"):
        assert role_call(c, "42", new_role).status_code == 403
    assert role_of("42") == "Owner"
    assert ENV.client().get(f"/api/my-role?guild_id={G1}").json()["role"] == "Owner"


def test_feste_inhaber_sind_unveraenderbar(monkeypatch):
    monkeypatch.setattr(botapp, "OWNER_DISCORD_IDS", {"42", "77"})
    ENV.set_role(G1, "Mitglied"); c = ENV.client()
    add_user("77", "Owner"); add_user("999", "Owner")                         # 77 = weiterer Inhaber aus der Variable, 999 = Discord-Serverbesitzer
    assert role_call(c, "77", "Mitglied").status_code == 403 and role_of("77") == "Owner"
    assert role_call(c, "999", "Mitglied").status_code == 403 and role_of("999") == "Owner"
    add_user("55", "Mitglied")
    assert role_call(c, "55", "Moderator").status_code == 200                 # normale Rollenverwaltung geht weiter


def test_rollenvergabe_schreibt_log_mit_namen():
    ENV.set_role(G1, "Owner"); add_user("99", "Mitglied"); c = ENV.client()
    role_call(c, "99", "Moderator")
    with SessionLocal() as db:
        from models import LogEntry
        assert any("u99" in l.text and "Moderator" in l.text for l in db.query(LogEntry).all())


# ------------------------------------------------------------------ Login und Serverliste
def test_eigene_discord_id_ist_gueltig():
    assert botapp._parse_discord_ids("1367572713509621780") == ({"1367572713509621780"}, [])


def test_login_gleicht_die_rolle_auf_allen_gemeinsamen_servern_sofort_ab(monkeypatch):
    monkeypatch.setattr(botapp, "OWNER_DISCORD_IDS", {"42"})
    guilds = [ENV._get_guild("1"), ENV._get_guild("2")]
    monkeypatch.setattr(type(botapp.bot), "guilds", property(lambda self: guilds))
    with SessionLocal() as db:
        botapp.refresh_roles_after_login(db, "42", "tester")                   # noch kein Benutzer in der Datenbank
    with SessionLocal() as db:
        assert db.get(User, "1:42").role == "Owner" and db.get(User, "2:42").role == "Owner"


def test_login_macht_normale_nutzer_nicht_zum_owner(monkeypatch):
    monkeypatch.setattr(botapp, "OWNER_DISCORD_IDS", {"999999999999999999"})
    monkeypatch.setattr(type(botapp.bot), "guilds", property(lambda self: [ENV._get_guild("1")]))
    with SessionLocal() as db:
        botapp.refresh_roles_after_login(db, "42", "tester")
    assert role_of("42") == "Mitglied"


def test_login_bleibt_stabil_wenn_der_abgleich_fehlschlaegt(monkeypatch):
    def kaputt(uid):
        raise RuntimeError("Cache kaputt")
    bad_guild = SimpleNamespace(id=1, owner_id=999, get_member=kaputt)
    monkeypatch.setattr(type(botapp.bot), "guilds", property(lambda self: [bad_guild]))
    with SessionLocal() as db:
        botapp.refresh_roles_after_login(db, "42", "tester")                   # darf keine Ausnahme auslösen


def test_serverliste_zeigt_feste_inhaber_sofort_als_owner(monkeypatch):
    monkeypatch.setattr(botapp, "OWNER_DISCORD_IDS", {"42"})
    ENV.set_role(G1, "Mitglied")                                               # in der Datenbank noch veraltet
    monkeypatch.setattr(type(botapp.bot), "guilds", property(lambda self: [ENV._get_guild("1")]))
    assert ENV.client().get("/api/my-guilds").json()[0]["my_role"] == "Owner"


def test_serverliste_normale_nutzer_behalten_ihre_rolle(monkeypatch):
    ENV.set_role(G1, "Support")
    monkeypatch.setattr(type(botapp.bot), "guilds", property(lambda self: [ENV._get_guild("1")]))
    assert ENV.client().get("/api/my-guilds").json()[0]["my_role"] == "Support"


def test_login_schreibt_diagnosezeile_in_die_konsole(monkeypatch, capsys):
    monkeypatch.setattr(botapp, "OWNER_DISCORD_IDS", {"42"})
    monkeypatch.setattr(type(botapp.bot), "guilds", property(lambda self: [ENV._get_guild("1")]))
    with SessionLocal() as db:
        botapp.refresh_roles_after_login(db, "42", "tester")
    out = capsys.readouterr().out
    assert "fester Inhaber laut OWNER_DISCORD_IDS: JA" in out and "auf 1 Server(n) als Mitglied erkannt" in out


def test_login_diagnose_nennt_fehlenden_members_intent(monkeypatch, capsys):
    monkeypatch.setattr(type(botapp.bot), "guilds", property(lambda self: [SimpleNamespace(id=1, owner_id=999, get_member=lambda uid: None)]))
    with SessionLocal() as db:
        botapp.refresh_roles_after_login(db, "42", "tester")
    out = capsys.readouterr().out
    assert "fester Inhaber laut OWNER_DISCORD_IDS: nein" in out and "Server Members Intent" in out


# ------------------------------------------------------------------ Einmalige Inhaber-Freischaltung (Bootstrap)
def test_bootstrap_id_aus_code_und_umgebung_wird_gelesen():
    assert botapp._parse_discord_ids("" + "," + "1367572713509621780") == ({"1367572713509621780"}, [])
    assert botapp._parse_discord_ids("123456789012345678" + "," + "") == ({"123456789012345678"}, [])


def test_bootstrap_macht_dauerhaft_zum_inhaber_auch_nach_entfernen(monkeypatch, capsys):
    monkeypatch.setattr(botapp, "OWNER_BOOTSTRAP_IDS", {"500"})
    add_user("500", "Mitglied")
    assert sync("500", fake_guild(500)) == "Owner"
    assert setting("owner_ernannt") == "500"
    assert "INHABER-FREISCHALTUNG" in capsys.readouterr().out
    monkeypatch.setattr(botapp, "OWNER_BOOTSTRAP_IDS", set())                  # Eintrag wieder entfernt, Neustart
    assert sync("500", fake_guild(500)) == "Owner"                             # bleibt Inhaber
    assert sync("500", fake_guild(500)) == "Owner"


def test_bootstrap_meldet_sich_nur_einmal_und_erzeugt_keine_doppelten_eintraege(monkeypatch, capsys):
    monkeypatch.setattr(botapp, "OWNER_BOOTSTRAP_IDS", {"500"})
    add_user("500", "Mitglied")
    for _ in range(3):
        sync("500", fake_guild(500))
    assert capsys.readouterr().out.count("INHABER-FREISCHALTUNG") == 1
    assert setting("owner_ernannt") == "500"


def test_bootstrap_betrifft_nur_eingetragene_nutzer(monkeypatch):
    monkeypatch.setattr(botapp, "OWNER_BOOTSTRAP_IDS", {"500"})
    add_user("501", "Mitglied")
    assert sync("501", fake_guild(501)) == "Mitglied" and setting("owner_ernannt") is None


def test_bootstrap_ueber_die_api_gilt_nach_entfernen_weiter(monkeypatch):
    monkeypatch.setattr(botapp, "OWNER_BOOTSTRAP_IDS", {"42"})
    ENV.set_role(G1, "Mitglied")
    assert ENV.client().get(f"/api/my-role?guild_id={G1}").json()["role"] == "Owner"
    monkeypatch.setattr(botapp, "OWNER_BOOTSTRAP_IDS", set())
    c = ENV.client()
    assert c.get(f"/api/my-role?guild_id={G1}").json()["role"] == "Owner"
    assert c.get(f"/api/settings?guild_id={G1}").status_code == 200            # Vollzugriff bleibt


def test_freigeschalteter_inhaber_laesst_sich_nur_von_anderem_inhaber_abstufen(monkeypatch):
    monkeypatch.setattr(botapp, "OWNER_BOOTSTRAP_IDS", {"42"})
    ENV.set_role(G1, "Mitglied"); c = ENV.client()
    c.get(f"/api/my-role?guild_id={G1}")
    assert role_call(c, "42", "Mitglied").status_code == 403                  # nicht selbst
    assert role_of("42") == "Owner"
    monkeypatch.setattr(botapp, "OWNER_BOOTSTRAP_IDS", set())
    add_user("99", "Mitglied")
    assert role_call(c, "99", "Owner").status_code == 200                      # ernannter Inhaber darf weitere ernennen
