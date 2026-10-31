"""
Zentrale Rechte-Tabelle für alle /api/-Endpunkte des Dashboards.

Prinzip: "alles verboten, was nicht freigegeben ist". Jeder Endpunkt steht genau einmal in PERMISSIONS
(Methode + Pfad-Vorlage -> Stufe). Ein Endpunkt, der hier fehlt, wird mit 403 abgelehnt (und der Test
tests/test_permissions.py schlägt fehl), damit nie wieder ein ungeschützter Endpunkt unbemerkt entsteht.

Stufen:
    public  - ohne Anmeldung
    login   - angemeldet (kein Server nötig)
    member  - angemeldet UND Mitglied des Servers (guild_id), Rolle egal ("Bewohner")
    team    - Support, Moderator, Admin, Owner
    admin   - Admin, Owner
Rollen kommen aus der Datenbank (Dashboard -> Benutzer) und werden bei jedem Zugriff mit Discord abgeglichen.
"""

ROLE_RANK = {"Mitglied": 0, "Member": 0, "Support": 1, "Moderator": 2, "Admin": 3, "Owner": 4}
LEVEL_MIN_RANK = {"member": 0, "team": 1, "admin": 3}

# Diese Pfade prüfen Anmeldung und Rolle selbst (eigene Admin-Prüfung im Modul) - das Modul bleibt unverändert.
SELF_CHECKED_PREFIXES = ("/api/ki", "/api/serverstat")

PERMISSIONS: dict[tuple[str, str], str] = {
    # --- öffentlich / angemeldet ---
    ("GET", "/api/public-status"): "public",
    ("GET", "/api/my-guilds"): "login",
    # --- Server-Grunddaten ---
    ("GET", "/api/guild-info"): "member",
    ("GET", "/api/my-role"): "member",
    ("GET", "/api/modules"): "member",
    ("GET", "/api/guild-channels"): "admin",
    ("GET", "/api/guild-roles"): "admin",
    ("GET", "/api/guild-categories"): "admin",
    # --- Startseiten je Rolle ---
    ("GET", "/api/me/dashboard"): "member",
    ("GET", "/api/me/tickets"): "member",
    ("GET", "/api/me/ausweis"): "member",
    ("POST", "/api/me/ausweis"): "member",
    ("GET", "/api/team/dashboard"): "team",
    ("GET", "/api/server/status"): "admin",
    ("GET", "/api/overview"): "team",
    # --- Bank (Überweisen/Ein-/Auszahlen wirkt immer nur auf das eigene Konto) ---
    ("GET", "/api/bank/accounts"): "admin",
    ("GET", "/api/bank/transactions"): "admin",
    ("POST", "/api/bank/transfer"): "member",
    ("POST", "/api/bank/deposit"): "member",
    ("POST", "/api/bank/withdraw"): "member",
    ("POST", "/api/users/{user_id}/balance"): "admin",
    # --- Shop ---
    ("GET", "/api/shop/items"): "member",
    ("POST", "/api/shop/items"): "admin",
    ("POST", "/api/shop/items/{item_id}"): "admin",
    ("DELETE", "/api/shop/items/{item_id}"): "admin",
    # --- Dienst ---
    ("GET", "/api/dienst"): "member",
    ("GET", "/api/dienst/me"): "member",
    ("POST", "/api/dienst/{fraction_id}/toggle"): "member",
    ("POST", "/api/dienst"): "admin",
    ("DELETE", "/api/dienst/{fraction_id}"): "admin",
    # --- Giveaways ---
    ("GET", "/api/giveaways"): "member",
    ("POST", "/api/giveaways"): "admin",
    ("POST", "/api/giveaways/{giveaway_id}/end"): "admin",
    ("POST", "/api/giveaways/{giveaway_id}/reroll"): "admin",
    # --- AFK (set/clear wirken nur auf das eigene Konto) ---
    ("GET", "/api/afk"): "member",
    ("GET", "/api/afk/me"): "member",
    ("POST", "/api/afk/set"): "member",
    ("POST", "/api/afk/clear"): "member",
    # --- Team-Werkzeuge ---
    ("GET", "/api/tickets"): "team",
    ("POST", "/api/tickets/{ticket_id}/close"): "team",
    ("GET", "/api/logs"): "team",
    ("GET", "/api/stats"): "team",
    ("GET", "/api/users"): "team",
    ("GET", "/api/team"): "team",
    ("GET", "/api/meetings"): "team",
    ("GET", "/api/todos"): "team",
    ("POST", "/api/todos"): "team",
    ("POST", "/api/todos/{todo_id}/toggle"): "team",
    ("DELETE", "/api/todos/{todo_id}"): "team",
    ("GET", "/api/ausweise"): "team",
    # --- Verwaltung ---
    ("POST", "/api/ausweise/{discord_id}"): "admin",
    ("POST", "/api/users/{user_id}/role"): "admin",
    ("GET", "/api/settings"): "admin",
    ("POST", "/api/settings"): "admin",
    ("POST", "/api/modules/{module_key}"): "admin",
    ("POST", "/api/announce"): "admin",
    ("POST", "/api/bot/sync"): "admin",
    # --- Sicherheit ---
    ("GET", "/api/security/overview"): "admin",
    ("GET", "/api/security/sessions"): "admin",
    ("POST", "/api/security/sessions/{session_id}/revoke"): "member",   # beendet nur eigene Sitzungen (im Endpunkt geprüft)
}


def role_rank(role: str | None) -> int:
    return ROLE_RANK.get(role or "Mitglied", 0)


def role_allows(role: str | None, level: str) -> bool:
    """True, wenn die Rolle die Stufe erfüllt."""
    return role_rank(role) >= LEVEL_MIN_RANK[level]


ASSIGNABLE_ROLES = ("Mitglied", "Support", "Moderator", "Admin")   # "Owner" ist immer der Discord-Server-Owner


def can_assign_role(actor_role: str | None, target_current_role: str | None, new_role: str) -> bool:
    """Wer darf wem welche Rolle geben?
    - Owner (Server-Eigentümer) darf alles außer die Owner-Rolle selbst zu ändern oder zu vergeben.
    - Admins verwalten bis Moderator; Admin-Rechte vergibt oder entzieht nur der Owner.
    - Der Server-Owner selbst bleibt immer Owner (wird von Discord vorgegeben)."""
    if new_role not in ASSIGNABLE_ROLES or role_rank(target_current_role) >= ROLE_RANK["Owner"]:
        return False
    actor = role_rank(actor_role)
    if actor >= ROLE_RANK["Owner"]:
        return True
    return actor >= ROLE_RANK["Admin"] and role_rank(target_current_role) < ROLE_RANK["Admin"] and ROLE_RANK[new_role] < ROLE_RANK["Admin"]
