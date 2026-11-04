"""Gemeinsame Test-Hilfen: meldet einen Test-Nutzer ECHT an (Cookie) und gibt ihm pro Server eine Rolle.
Die Rechteprüfung (permissions.py) wird dabei nie umgangen."""
from datetime import datetime, timezone
from types import SimpleNamespace

import jwt
from fastapi.testclient import TestClient

ADMIN_ROLE_ID = 555


class AuthEnv:
    def __init__(self, botapp, monkeypatch, user_id="42", username="tester"):
        self.botapp, self.user_id, self.username = botapp, user_id, username
        self.roles = {}            # guild_id -> Rolle des Test-Nutzers
        self.guilds = None         # None = Nutzer ist auf jedem Server Mitglied, sonst Menge erlaubter Server-IDs
        self.extra_members = {}    # discord_id (int) -> weiteres Mitglied (z. B. SimpleNamespace(display_name="X"))
        monkeypatch.setattr(botapp.bot, "get_guild", self._get_guild)

    def _get_guild(self, gid):
        gid = str(gid)
        if self.guilds is not None and gid not in self.guilds:
            return None
        role = self.roles.get(gid, "Mitglied")
        me = SimpleNamespace(id=int(self.user_id), display_name=self.username, bot=False, name=self.username, joined_at=datetime.now(timezone.utc),
                             roles=[SimpleNamespace(id=ADMIN_ROLE_ID)] if role == "Admin" else [])
        members = {int(self.user_id): me, **self.extra_members}
        return SimpleNamespace(id=int(gid), name=f"Server {gid}", icon=None, member_count=len(members) + 20,
                               members=list(members.values()), roles=[SimpleNamespace(id=1)], owner_id=int(self.user_id) if role == "Owner" else 999,
                               get_member=lambda uid: members.get(uid))

    def set_role(self, guild_id, role):
        from database import SessionLocal
        from models import Setting, User
        guild_id = str(guild_id)
        self.roles[guild_id] = role
        with SessionLocal() as db:
            if role == "Admin":                       # Discord-Admin-Rolle, damit der Rollen-Abgleich sie bestehen lässt
                key = f"{guild_id}:admin_rolle"
                s = db.get(Setting, key)
                if s:
                    s.value = str(ADMIN_ROLE_ID)
                else:
                    db.add(Setting(key=key, value=str(ADMIN_ROLE_ID)))
            uid = f"{guild_id}:{self.user_id}"
            u = db.get(User, uid)
            if u:
                u.role = role
            else:
                db.add(User(id=uid, guild_id=guild_id, discord_id=self.user_id, username=self.username, role=role))
            db.commit()

    def client(self, app=None, raise_server_exceptions=True):
        c = TestClient(app or self.botapp.app, raise_server_exceptions=raise_server_exceptions)
        c.cookies.set("session", jwt.encode({"sub": self.user_id, "username": self.username}, self.botapp.JWT_SECRET, algorithm="HS256"))
        return c
