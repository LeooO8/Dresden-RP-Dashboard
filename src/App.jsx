import React, { useState, useMemo, useEffect, createContext, useContext } from "react";
import {
  LayoutDashboard, Landmark, ShoppingBag, ShieldHalf, Gift, ScrollText,
  Settings, Users, BarChart3, Lock, Circle, ArrowUpRight, ArrowDownRight,
  Search, Plus, Pencil, Trash2, Power, Clock, Coins, Wallet, TrendingUp,
  KeyRound, LogIn, ChevronRight, Activity, WifiOff, Wifi
} from "lucide-react";

/* ---------------------------------------------------------
   API-VERBINDUNG
   Trage hier die Adresse deines Backends ein (siehe README).
   Solange die API nicht erreichbar ist, bleiben alle Bereiche
   mit den Beispieldaten unten voll funktionsfähig ("Demo-Modus").
--------------------------------------------------------- */
const API_BASE = "https://web-production-fdbea.up.railway.app";

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  return res.json();
}

async function apiPostQuery(path, params) {
  const qs = new URLSearchParams(params || {}).toString();
  const res = await fetch(`${API_BASE}${path}${qs ? `?${qs}` : ""}`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  return res.json();
}

async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  return res.json();
}

const LiveContext = createContext({ live: false, user: null });
const useLive = () => useContext(LiveContext);

/* ---------------------------------------------------------
   THEME TOKENS
   bg #0A0E13 · panel #12181F · panelAlt #171F2A · border #232D3B
   text #E7ECF2 · muted #7C8798
   gold #F2B705 (Ökonomie) · cyan #38BDF8 (Status) · green #4ADE80 (on)
   red #FB5B5B (off/danger)
--------------------------------------------------------- */
const C = {
  bg: "#0A0E13",
  panel: "#121821",
  panelAlt: "#171F2A",
  border: "#232D3B",
  text: "#E7ECF2",
  muted: "#7C8798",
  gold: "#F2B705",
  cyan: "#38BDF8",
  green: "#4ADE80",
  red: "#FB5B5B",
};

const fmtMoney = (n) =>
  n.toLocaleString("de-DE", { minimumFractionDigits: 0 }) + " ₡";

/* ---------------------------------------------------------
   MOCK DATA
--------------------------------------------------------- */
const USERS = [];

const TRANSACTIONS = [];

const SHOP_ITEMS = [];

const DUTY = [];

const GIVEAWAYS = [];

const LOGS = [];

const LOG_META = {
  bank: { label: "Bank", color: C.gold },
  shop: { label: "Shop", color: C.cyan },
  dienst: { label: "Dienst", color: C.green },
  login: { label: "Login", color: "#B79CFF" },
  system: { label: "System", color: C.muted },
};

const NAV = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "bank", label: "Bank-System", icon: Landmark },
  { key: "shop", label: "Shop-System", icon: ShoppingBag },
  { key: "dienst", label: "Dienstsystem", icon: ShieldHalf },
  { key: "giveaway", label: "Giveaways", icon: Gift },
  { key: "logs", label: "Audit Logs", icon: ScrollText },
  { key: "stats", label: "Statistiken", icon: BarChart3 },
  { key: "users", label: "Benutzerverwaltung", icon: Users },
  { key: "security", label: "Sicherheit", icon: Lock },
  { key: "settings", label: "Einstellungen", icon: Settings },
];

/* ---------------------------------------------------------
   PRIMITIVES
--------------------------------------------------------- */
function Panel({ children, style, ...rest }) {
  return (
    <div
      style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 10, ...style }}
      {...rest}
    >
      {children}
    </div>
  );
}

function Badge({ children, color = C.muted, bg }) {
  return (
    <span
      style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        fontFamily: "'JetBrains Mono', monospace", fontSize: 11, fontWeight: 600,
        color, background: bg || `${color}1A`, border: `1px solid ${color}40`,
        padding: "3px 8px", borderRadius: 5, letterSpacing: 0.3,
      }}
    >
      {children}
    </span>
  );
}

function StatusDot({ status }) {
  const col = status === "online" ? C.green : status === "idle" ? C.gold : C.muted;
  return <Circle size={8} style={{ fill: col, color: col }} />;
}

function SectionTitle({ eyebrow, title, action }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 20 }}>
      <div>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: C.gold, letterSpacing: 1.5, marginBottom: 4, textTransform: "uppercase" }}>
          {eyebrow}
        </div>
        <h1 style={{ fontFamily: "'Rajdhani', sans-serif", fontSize: 28, fontWeight: 700, color: C.text, margin: 0, letterSpacing: 0.3 }}>
          {title}
        </h1>
      </div>
      {action}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, delta, deltaUp, accent = C.gold }) {
  return (
    <Panel style={{ padding: 18, flex: 1, minWidth: 160 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div style={{ width: 34, height: 34, borderRadius: 8, background: `${accent}1A`, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Icon size={17} color={accent} />
        </div>
        {delta && (
          <span style={{ display: "flex", alignItems: "center", gap: 2, fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: deltaUp ? C.green : C.red }}>
            {deltaUp ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}{delta}
          </span>
        )}
      </div>
      <div style={{ fontFamily: "'Rajdhani', sans-serif", fontSize: 26, fontWeight: 700, color: C.text, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 12.5, color: C.muted, marginTop: 6 }}>{label}</div>
    </Panel>
  );
}

function Th({ children, align }) {
  return (
    <th style={{
      textAlign: align || "left", fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5,
      color: C.muted, textTransform: "uppercase", letterSpacing: 1, padding: "0 14px 10px",
      fontWeight: 500, borderBottom: `1px solid ${C.border}`,
    }}>
      {children}
    </th>
  );
}
function Td({ children, align, style }) {
  return (
    <td style={{ padding: "13px 14px", fontSize: 13.5, color: C.text, textAlign: align || "left", borderBottom: `1px solid ${C.border}`, ...style }}>
      {children}
    </td>
  );
}

function IconBtn({ icon: Icon, danger, ...rest }) {
  return (
    <button
      {...rest}
      style={{
        width: 28, height: 28, borderRadius: 6, border: `1px solid ${C.border}`,
        background: "transparent", display: "inline-flex", alignItems: "center", justifyContent: "center",
        color: danger ? C.red : C.muted, cursor: "pointer",
        ...rest.style,
      }}>
      <Icon size={13} />
    </button>
  );
}

function PrimaryBtn({ children, icon: Icon, ...rest }) {
  return (
    <button
      {...rest}
      style={{
        display: "flex", alignItems: "center", gap: 7, background: C.gold, color: "#1A1400",
        border: "none", borderRadius: 7, padding: "9px 15px", fontWeight: 700, fontSize: 13,
        fontFamily: "'Rajdhani', sans-serif", letterSpacing: 0.3, cursor: "pointer",
        ...rest.style,
      }}>
      {Icon && <Icon size={15} />} {children}
    </button>
  );
}

/* ---------------------------------------------------------
   HUD TICKER (signature element)
--------------------------------------------------------- */
function Ticker({ overview }) {
  const { live, user } = useLive();
  const items = [
    { label: "BOT-STATUS", value: overview ? overview.bot_status?.toUpperCase() : "ONLINE", color: C.green },
    { label: "MITGLIEDER", value: overview ? overview.member_count.toLocaleString("de-DE") : "0", color: C.text },
    { label: "IM DIENST", value: overview ? overview.on_duty : "7", color: C.cyan },
    { label: "GESAMTGUTHABEN", value: fmtMoney(overview ? overview.total_balance : 0), color: C.gold },
    { label: "UPTIME", value: "14T 6H 22M", color: C.text },
  ];
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between", gap: 20,
      background: C.panelAlt, borderBottom: `1px solid ${C.border}`,
      padding: "9px 24px", fontFamily: "'JetBrains Mono', monospace",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 28, overflowX: "auto" }}>
        {items.map((it, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, whiteSpace: "nowrap" }}>
            <span style={{ width: 6, height: 6, borderRadius: 99, background: it.color, boxShadow: `0 0 6px ${it.color}` }} />
            <span style={{ fontSize: 10, color: C.muted, letterSpacing: 1 }}>{it.label}</span>
            <span style={{ fontSize: 12, color: it.color, fontWeight: 700 }}>{it.value}</span>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
        <span style={{
          display: "flex", alignItems: "center", gap: 6, fontSize: 10.5, letterSpacing: 0.5,
          color: live ? C.green : C.muted, border: `1px solid ${live ? C.green : C.border}`,
          borderRadius: 5, padding: "3px 8px",
        }}>
          {live ? <Wifi size={11} /> : <WifiOff size={11} />}
          {live ? "LIVE VERBUNDEN" : "DEMO-DATEN"}
        </span>
        {live && user ? (
          <span style={{ fontSize: 11.5, color: C.text }}>{user.username}</span>
        ) : (
          <a href={`${API_BASE}/auth/login`} style={{
            display: "flex", alignItems: "center", gap: 5, fontSize: 11.5, color: "#1A1400",
            background: C.gold, borderRadius: 5, padding: "5px 10px", fontWeight: 700,
            textDecoration: "none", fontFamily: "'Rajdhani', sans-serif",
          }}>
            <LogIn size={12} /> Mit Discord anmelden
          </a>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------
   SECTIONS
--------------------------------------------------------- */
function DashboardSection() {
  return (
    <>
      <SectionTitle eyebrow="Systemübersicht" title="Dashboard" />
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 14 }}>
        <StatCard icon={Users} label="Mitglieder gesamt" value="0" accent={C.cyan} />
        <StatCard icon={ShieldHalf} label="Aktive Dienste" value="7" delta="+2" deltaUp accent={C.green} />
        <StatCard icon={Coins} label="Gesamtguthaben" value={fmtMoney(0)} accent={C.gold} />
        <StatCard icon={Activity} label="Bot-Uptime" value="0%" accent={C.text} />
      </div>
      <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
        <Panel style={{ padding: 18, flex: 2 }}>
          <div style={{ fontFamily: "'Rajdhani', sans-serif", fontWeight: 700, fontSize: 16, color: C.text, marginBottom: 14 }}>
            Live-Systemstatus
          </div>
          {[
            { name: "Discord Gateway", ok: true },
            { name: "Bank-System", ok: true },
            { name: "Shop-System", ok: true },
            { name: "Dienstsystem", ok: true },
            { name: "Datenbank", ok: true },
            { name: "OAuth2 Login", ok: true },
          ].map((s, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "9px 0", borderBottom: i < 5 ? `1px solid ${C.border}` : "none" }}>
              <span style={{ fontSize: 13.5, color: C.text }}>{s.name}</span>
              <Badge color={C.green}><StatusDot status="online" /> Betriebsbereit</Badge>
            </div>
          ))}
        </Panel>
        <Panel style={{ padding: 18, flex: 1 }}>
          <div style={{ fontFamily: "'Rajdhani', sans-serif", fontWeight: 700, fontSize: 16, color: C.text, marginBottom: 14 }}>
            Letzte Aktionen
          </div>
          {LOGS.slice(0, 5).map((l) => (
            <div key={l.id} style={{ display: "flex", gap: 9, alignItems: "flex-start", padding: "8px 0", borderBottom: `1px solid ${C.border}` }}>
              <span style={{ width: 6, height: 6, marginTop: 5, borderRadius: 99, background: LOG_META[l.type].color, flexShrink: 0 }} />
              <div>
                <div style={{ fontSize: 12.5, color: C.text, lineHeight: 1.4 }}>{l.text}</div>
                <div style={{ fontSize: 10.5, color: C.muted, marginTop: 2, fontFamily: "'JetBrains Mono', monospace" }}>{l.time}</div>
              </div>
            </div>
          ))}
        </Panel>
      </div>
    </>
  );
}

function BankSection() {
  const { live } = useLive();
  const [startBalance, setStartBalance] = useState(500);
  const [accounts, setAccounts] = useState(USERS);
  const [txns, setTxns] = useState(TRANSACTIONS);

  useEffect(() => {
    if (!live) return;
    apiGet("/api/bank/accounts").then(setAccounts).catch(() => {});
    apiGet("/api/bank/transactions").then(setTxns).catch(() => {});
  }, [live]);

  return (
    <>
      <SectionTitle eyebrow="Wirtschaft" title="Bank-System" action={<PrimaryBtn icon={Plus}>Konto verwalten</PrimaryBtn>} />
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 20 }}>
        <StatCard icon={Wallet} label="Gesamtguthaben aller Nutzer" value={fmtMoney(0)} accent={C.gold} />
        <StatCard icon={TrendingUp} label="Umsatz heute" value={fmtMoney(48200)} delta="+6,4%" deltaUp accent={C.green} />
        <Panel style={{ padding: 18, flex: 1, minWidth: 220 }}>
          <div style={{ fontSize: 12.5, color: C.muted, marginBottom: 10 }}>Startguthaben (frei einstellbar)</div>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              type="number" value={startBalance} onChange={(e) => setStartBalance(e.target.value)}
              style={{ flex: 1, background: C.panelAlt, border: `1px solid ${C.border}`, borderRadius: 6, padding: "8px 10px", color: C.text, fontFamily: "'JetBrains Mono', monospace", fontSize: 13 }}
            />
            <PrimaryBtn>Speichern</PrimaryBtn>
          </div>
        </Panel>
      </div>

      <div style={{ fontFamily: "'Rajdhani', sans-serif", fontWeight: 700, fontSize: 16, color: C.text, marginBottom: 10 }}>Konten</div>
      <Panel style={{ overflow: "hidden", marginBottom: 20 }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr><Th>Benutzer</Th><Th>Kontostand</Th><Th>Rolle</Th><Th align="right">Aktion</Th></tr></thead>
          <tbody>
            {accounts.map((u) => (
              <tr key={u.id}>
                <Td>{u.name}</Td>
                <Td style={{ fontFamily: "'JetBrains Mono', monospace", color: C.gold }}>{fmtMoney(u.balance)}</Td>
                <Td><span style={{ color: C.muted }}>{u.role}</span></Td>
                <Td align="right"><IconBtn icon={Pencil} /></Td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <div style={{ fontFamily: "'Rajdhani', sans-serif", fontWeight: 700, fontSize: 16, color: C.text, marginBottom: 10 }}>Transaktionsverlauf</div>
      <Panel style={{ overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr><Th>Von</Th><Th>An</Th><Th>Typ</Th><Th align="right">Betrag</Th><Th align="right">Zeit</Th></tr></thead>
          <tbody>
            {txns.map((t) => (
              <tr key={t.id}>
                <Td>{t.from}</Td><Td>{t.to}</Td>
                <Td><Badge color={C.cyan}>{t.type}</Badge></Td>
                <Td align="right" style={{ fontFamily: "'JetBrains Mono', monospace", color: C.gold }}>{fmtMoney(t.amount)}</Td>
                <Td align="right" style={{ color: C.muted, fontSize: 12 }}>{t.time}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </>
  );
}

function ShopSection() {
  const cats = [...new Set(SHOP_ITEMS.map((i) => i.category))];
  return (
    <>
      <SectionTitle eyebrow="Wirtschaft" title="Shop-System" action={<PrimaryBtn icon={Plus}>Artikel erstellen</PrimaryBtn>} />
      <div style={{ display: "flex", gap: 8, marginBottom: 18 }}>
        {cats.map((c) => <Badge key={c} color={C.gold}>{c}</Badge>)}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 14 }}>
        {SHOP_ITEMS.map((it) => (
          <Panel key={it.id} style={{ padding: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
              <Badge color={C.cyan}>{it.category}</Badge>
              <div style={{ display: "flex", gap: 6 }}>
                <IconBtn icon={Pencil} /><IconBtn icon={Trash2} danger />
              </div>
            </div>
            <div style={{ fontFamily: "'Rajdhani', sans-serif", fontWeight: 700, fontSize: 17, color: C.text, marginBottom: 6 }}>{it.name}</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", color: C.gold, fontSize: 15, fontWeight: 700 }}>{fmtMoney(it.price)}</div>
            <div style={{ fontSize: 11.5, color: C.muted, marginTop: 4 }}>{it.sold}× verkauft</div>
          </Panel>
        ))}
      </div>
    </>
  );
}

function DienstSection() {
  const { live } = useLive();
  const [duty, setDuty] = useState(DUTY);
  const [newName, setNewName] = useState("");
  const [newTotal, setNewTotal] = useState(5);

  const refresh = () => apiGet("/api/dienst").then(setDuty).catch(() => {});

  useEffect(() => {
    if (!live) return;
    refresh();
  }, [live]);

  const toggle = (d) => {
    if (!live) {
      setDuty(duty.map((x) => x.id === d.id ? { ...x, onDuty: x.onDuty > 0 ? 0 : Math.min(1, x.total) } : x));
      return;
    }
    apiPostQuery(`/api/dienst/${d.id}/toggle`, {}).then(refresh)
      .catch(() => alert("Fehlgeschlagen — bist du mit Discord angemeldet?"));
  };

  const createFraction = () => {
    if (!newName.trim()) return;
    if (!live) {
      setDuty([...duty, { id: Date.now(), fraction: newName, onDuty: 0, total: Number(newTotal), hoursToday: 0 }]);
      setNewName(""); setNewTotal(5);
      return;
    }
    apiPostQuery("/api/dienst", { name: newName, total: newTotal })
      .then(() => { setNewName(""); setNewTotal(5); refresh(); })
      .catch(() => alert("Fehlgeschlagen — bist du mit Discord angemeldet?"));
  };

  const removeFraction = (d) => {
    if (!live) { setDuty(duty.filter((x) => x.id !== d.id)); return; }
    apiDelete(`/api/dienst/${d.id}`).then(refresh)
      .catch(() => alert("Fehlgeschlagen — bist du mit Discord angemeldet?"));
  };

  return (
    <>
      <SectionTitle eyebrow="Fraktionen" title="Dienstsystem" />
      <Panel style={{ padding: 16, marginBottom: 18, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <input
          value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Name der Fraktion (z.B. Polizei)"
          style={{ flex: 2, minWidth: 180, background: C.panelAlt, border: `1px solid ${C.border}`, borderRadius: 6, padding: "8px 10px", color: C.text, fontSize: 13 }}
        />
        <input
          type="number" value={newTotal} onChange={(e) => setNewTotal(e.target.value)} placeholder="Plätze"
          style={{ width: 90, background: C.panelAlt, border: `1px solid ${C.border}`, borderRadius: 6, padding: "8px 10px", color: C.text, fontSize: 13 }}
        />
        <PrimaryBtn icon={Plus} onClick={createFraction}>Fraktion anlegen</PrimaryBtn>
      </Panel>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px,1fr))", gap: 14 }}>
        {duty.map((d) => (
          <Panel key={d.id || d.fraction} style={{ padding: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <div style={{ fontFamily: "'Rajdhani', sans-serif", fontWeight: 700, fontSize: 16, color: C.text }}>{d.fraction}</div>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  onClick={() => toggle(d)}
                  style={{
                    display: "flex", alignItems: "center", gap: 5, border: `1px solid ${d.onDuty > 0 ? C.green : C.border}`,
                    background: d.onDuty > 0 ? `${C.green}1A` : "transparent", color: d.onDuty > 0 ? C.green : C.muted,
                    borderRadius: 6, padding: "5px 9px", fontSize: 11, cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
                  }}>
                  <Power size={12} /> {d.onDuty > 0 ? "IM DIENST" : "AUSSER DIENST"}
                </button>
                <IconBtn icon={Trash2} danger onClick={() => removeFraction(d)} />
              </div>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, color: C.muted, marginBottom: 6 }}>
              <span>{d.onDuty} / {d.total} im Dienst</span>
              <span><Clock size={11} style={{ display: "inline", marginRight: 3 }} />{d.hoursToday}h heute</span>
            </div>
            <div style={{ height: 6, background: C.panelAlt, borderRadius: 99, overflow: "hidden" }}>
              <div style={{ width: `${(d.onDuty / d.total) * 100}%`, height: "100%", background: C.cyan }} />
            </div>
          </Panel>
        ))}
      </div>
    </>
  );
}


function GiveawaySection() {
  return (
    <>
      <SectionTitle eyebrow="Community" title="Giveaway-System" action={<PrimaryBtn icon={Plus}>Giveaway erstellen</PrimaryBtn>} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px,1fr))", gap: 14 }}>
        {GIVEAWAYS.map((g) => (
          <Panel key={g.id} style={{ padding: 18 }}>
            <div style={{ marginBottom: 10 }}>
              <Badge color={g.status === "aktiv" ? C.green : C.muted}>{g.status === "aktiv" ? "Aktiv" : "Beendet"}</Badge>
            </div>
            <div style={{ fontFamily: "'Rajdhani', sans-serif", fontWeight: 700, fontSize: 17, color: C.text, marginBottom: 8 }}>{g.prize}</div>
            <div style={{ fontSize: 12.5, color: C.muted, marginBottom: 4 }}>{g.entries} Teilnahmen</div>
            <div style={{ fontSize: 12.5, color: C.muted }}>{g.status === "aktiv" ? `Endet ${g.ends}` : `Gewinner: ${g.winner}`}</div>
          </Panel>
        ))}
      </div>
    </>
  );
}

function LogsSection() {
  const { live } = useLive();
  const [filter, setFilter] = useState("alle");
  const [logList, setLogList] = useState(LOGS);
  const types = ["alle", ...Object.keys(LOG_META)];

  useEffect(() => {
    if (!live) return;
    apiGet(`/api/logs?type=${filter}`).then(setLogList).catch(() => {});
  }, [live, filter]);

  const filtered = live ? logList : (filter === "alle" ? LOGS : LOGS.filter((l) => l.type === filter));
  return (
    <>
      <SectionTitle eyebrow="Protokoll" title="Audit Logs" />
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {types.map((t) => (
          <button key={t} onClick={() => setFilter(t)} style={{
            padding: "6px 12px", borderRadius: 6, fontSize: 12, cursor: "pointer",
            fontFamily: "'JetBrains Mono', monospace", textTransform: "capitalize",
            border: `1px solid ${filter === t ? C.gold : C.border}`,
            background: filter === t ? `${C.gold}1A` : "transparent",
            color: filter === t ? C.gold : C.muted,
          }}>
            {t === "alle" ? "Alle" : LOG_META[t].label}
          </button>
        ))}
      </div>
      <Panel style={{ overflow: "hidden" }}>
        {filtered.map((l, i) => (
          <div key={l.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", borderBottom: i < filtered.length - 1 ? `1px solid ${C.border}` : "none" }}>
            <Badge color={LOG_META[l.type].color}>{LOG_META[l.type].label}</Badge>
            <span style={{ flex: 1, fontSize: 13, color: C.text }}>{l.text}</span>
            <span style={{ fontSize: 11.5, color: C.muted, fontFamily: "'JetBrains Mono', monospace" }}>{l.time}</span>
          </div>
        ))}
      </Panel>
    </>
  );
}

function StatsSection() {
  const bars = [0, 0, 0, 0, 0, 0, 0];
  const days = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
  return (
    <>
      <SectionTitle eyebrow="Auswertung" title="Statistiken" />
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 18 }}>
        <StatCard icon={Users} label="Mitglieder" value="0" accent={C.cyan} />
        <StatCard icon={Activity} label="Aktive Nutzer (7T)" value="0" accent={C.green} />
        <StatCard icon={Coins} label="Gesamtvermögen" value={fmtMoney(0)} accent={C.gold} />
        <StatCard icon={ShoppingBag} label="Shop-Verkäufe" value="0" accent={C.cyan} />
        <StatCard icon={Clock} label="Dienststunden (heute)" value="0h" accent={C.green} />
        <StatCard icon={Gift} label="Giveaways gesamt" value="0" accent={C.gold} />
      </div>
      <Panel style={{ padding: 20 }}>
        <div style={{ fontFamily: "'Rajdhani', sans-serif", fontWeight: 700, fontSize: 16, color: C.text, marginBottom: 18 }}>
          Aktivität diese Woche
        </div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 14, height: 140 }}>
          {bars.map((h, i) => (
            <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
              <div style={{ width: "100%", height: `${h}%`, borderRadius: "4px 4px 0 0", background: `linear-gradient(to top, ${C.gold}, ${C.cyan})` }} />
              <span style={{ fontSize: 11, color: C.muted, fontFamily: "'JetBrains Mono', monospace" }}>{days[i]}</span>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}

function UsersSection() {
  const { live } = useLive();
  const [q, setQ] = useState("");
  const [userList, setUserList] = useState(USERS);

  useEffect(() => {
    if (!live) return;
    apiGet("/api/users").then(setUserList).catch(() => {});
  }, [live]);

  const filtered = userList.filter((u) => u.name.toLowerCase().includes(q.toLowerCase()));
  return (
    <>
      <SectionTitle eyebrow="Verwaltung" title="Benutzerverwaltung" />
      <div style={{ position: "relative", marginBottom: 16, maxWidth: 320 }}>
        <Search size={15} style={{ position: "absolute", left: 11, top: 10, color: C.muted }} />
        <input
          value={q} onChange={(e) => setQ(e.target.value)} placeholder="Benutzer suchen…"
          style={{ width: "100%", background: C.panelAlt, border: `1px solid ${C.border}`, borderRadius: 7, padding: "9px 12px 9px 32px", color: C.text, fontSize: 13 }}
        />
      </div>
      <Panel style={{ overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr><Th>Benutzer</Th><Th>Status</Th><Th>Rolle</Th><Th>Kontostand</Th><Th>Beigetreten</Th><Th align="right">Aktion</Th></tr></thead>
          <tbody>
            {filtered.map((u) => (
              <tr key={u.id}>
                <Td>
                  <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                    <div style={{ width: 26, height: 26, borderRadius: 7, background: C.panelAlt, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, color: C.gold, fontFamily: "'Rajdhani', sans-serif" }}>
                      {u.avatar}
                    </div>
                    {u.name}
                  </div>
                </Td>
                <Td><span style={{ display: "flex", alignItems: "center", gap: 6 }}><StatusDot status={u.status} /><span style={{ color: C.muted, fontSize: 12, textTransform: "capitalize" }}>{u.status}</span></span></Td>
                <Td style={{ color: C.muted, fontSize: 12.5 }}>{u.role}</Td>
                <Td style={{ fontFamily: "'JetBrains Mono', monospace", color: C.gold }}>{fmtMoney(u.balance)}</Td>
                <Td style={{ color: C.muted, fontSize: 12 }}>{u.joined}</Td>
                <Td align="right">
                  <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                    <IconBtn icon={Plus} /><IconBtn icon={Pencil} />
                  </div>
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </>
  );
}

function SecuritySection() {
  const sessions = [];
  return (
    <>
      <SectionTitle eyebrow="Zugriff" title="Sicherheit" />
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 18 }}>
        <Panel style={{ padding: 18, flex: 1, minWidth: 220 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <LogIn size={16} color={C.cyan} />
            <span style={{ fontFamily: "'Rajdhani', sans-serif", fontWeight: 700, color: C.text }}>Discord Login</span>
          </div>
          <div style={{ fontSize: 12.5, color: C.muted, lineHeight: 1.6 }}>Anmeldung über OAuth2 · verbunden mit dem Server</div>
          <div style={{ marginTop: 10 }}><Badge color={C.green}>Aktiv</Badge></div>
        </Panel>
        <Panel style={{ padding: 18, flex: 1, minWidth: 220 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <KeyRound size={16} color={C.gold} />
            <span style={{ fontFamily: "'Rajdhani', sans-serif", fontWeight: 700, color: C.text }}>Admin-Berechtigungen</span>
          </div>
          <div style={{ fontSize: 12.5, color: C.muted, lineHeight: 1.6 }}>3 Rollen mit Verwaltungszugriff konfiguriert</div>
        </Panel>
      </div>
      <div style={{ fontFamily: "'Rajdhani', sans-serif", fontWeight: 700, fontSize: 16, color: C.text, marginBottom: 10 }}>Aktive Sitzungen</div>
      <Panel style={{ overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr><Th>Benutzer</Th><Th>Gerät</Th><Th>IP-Adresse</Th><Th align="right">Letzte Aktivität</Th></tr></thead>
          <tbody>
            {sessions.map((s, i) => (
              <tr key={i}>
                <Td>{s.user}</Td><Td style={{ color: C.muted }}>{s.device}</Td>
                <Td style={{ fontFamily: "'JetBrains Mono', monospace", color: C.muted, fontSize: 12 }}>{s.ip}</Td>
                <Td align="right" style={{ color: C.muted, fontSize: 12 }}>{s.time}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </>
  );
}

function SettingsSection() {
  const groups = [
    { title: "Bot-Einstellungen", fields: ["Bot-Präfix", "Standard-Sprache", "Log-Kanal"] },
    { title: "Bank-Einstellungen", fields: ["Startguthaben", "Max. Überweisungsbetrag", "Zinssatz (täglich)"] },
    { title: "Shop-Einstellungen", fields: ["Standardkategorie", "Kaufbestätigung erforderlich"] },
    { title: "Dienst-Einstellungen", fields: ["Vergütung pro Stunde", "Automatischer Dienstende nach"] },
    { title: "Rollen & Kanäle", fields: ["Admin-Rolle", "Ankündigungskanal", "Log-Kanal"] },
  ];
  return (
    <>
      <SectionTitle eyebrow="Konfiguration" title="Einstellungen" />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px,1fr))", gap: 14 }}>
        {groups.map((g) => (
          <Panel key={g.title} style={{ padding: 18 }}>
            <div style={{ fontFamily: "'Rajdhani', sans-serif", fontWeight: 700, fontSize: 15, color: C.text, marginBottom: 14 }}>{g.title}</div>
            {g.fields.map((f) => (
              <div key={f} style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 11.5, color: C.muted, marginBottom: 5 }}>{f}</div>
                <input style={{ width: "100%", background: C.panelAlt, border: `1px solid ${C.border}`, borderRadius: 6, padding: "8px 10px", color: C.text, fontSize: 12.5, fontFamily: "'JetBrains Mono', monospace" }} placeholder="—" />
              </div>
            ))}
            <PrimaryBtn>Speichern</PrimaryBtn>
          </Panel>
        ))}
      </div>
    </>
  );
}

const SECTIONS = {
  dashboard: DashboardSection, bank: BankSection, shop: ShopSection, dienst: DienstSection,
  giveaway: GiveawaySection, logs: LogsSection, stats: StatsSection, users: UsersSection,
  security: SecuritySection, settings: SettingsSection,
};

/* ---------------------------------------------------------
   APP
--------------------------------------------------------- */
export default function DiscordBotDashboard() {
  const [active, setActive] = useState("dashboard");
  const [live, setLive] = useState(false);
  const [user, setUser] = useState(null);
  const [overview, setOverview] = useState(null);
  const Active = SECTIONS[active];

  useEffect(() => {
    let cancelled = false;
    // Verbindungscheck: klappt der Aufruf, ist die API erreichbar -> Live-Modus.
    apiGet("/api/overview")
      .then((data) => {
        if (cancelled) return;
        setOverview(data);
        setLive(true);
      })
      .catch(() => {
        // Backend nicht erreichbar -> Dashboard bleibt im Demo-Modus mit Beispieldaten.
        setLive(false);
      });
    apiGet("/auth/me").then((u) => !cancelled && setUser(u)).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  return (
    <LiveContext.Provider value={{ live, user }}>
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, fontFamily: "'Inter', sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
        * { box-sizing: border-box; }
        input:focus { outline: none; border-color: ${C.gold} !important; }
        ::-webkit-scrollbar { height: 6px; width: 6px; }
        ::-webkit-scrollbar-thumb { background: ${C.border}; border-radius: 99px; }
      `}</style>

      <Ticker overview={overview} />

      <div style={{ display: "flex" }}>
        {/* Sidebar */}
        <div style={{ width: 232, flexShrink: 0, borderRight: `1px solid ${C.border}`, minHeight: "calc(100vh - 40px)", padding: "20px 12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0 8px", marginBottom: 26 }}>
            <div style={{ width: 34, height: 34, borderRadius: 8, background: `linear-gradient(135deg, ${C.gold}, ${C.cyan})`, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontFamily: "'Rajdhani', sans-serif", color: "#0A0E13", fontSize: 15 }}>
              ⌁
            </div>
            <div>
              <div style={{ fontFamily: "'Rajdhani', sans-serif", fontWeight: 700, fontSize: 15, letterSpacing: 0.3 }}>DIENSTKONTROLLE</div>
              <div style={{ fontSize: 10, color: C.muted, fontFamily: "'JetBrains Mono', monospace" }}>Server Control Panel</div>
            </div>
          </div>

          {NAV.map((n) => {
            const Icon = n.icon;
            const isActive = active === n.key;
            return (
              <button
                key={n.key}
                onClick={() => setActive(n.key)}
                style={{
                  display: "flex", alignItems: "center", gap: 10, width: "100%",
                  padding: "9px 10px", marginBottom: 2, borderRadius: 7, border: "none",
                  background: isActive ? `${C.gold}14` : "transparent",
                  color: isActive ? C.gold : C.muted, cursor: "pointer",
                  fontSize: 13.5, fontFamily: "'Inter', sans-serif", fontWeight: isActive ? 600 : 500,
                  borderLeft: isActive ? `2px solid ${C.gold}` : "2px solid transparent",
                  textAlign: "left",
                }}
              >
                <Icon size={16} />
                {n.label}
                {isActive && <ChevronRight size={13} style={{ marginLeft: "auto" }} />}
              </button>
            );
          })}
        </div>

        {/* Main */}
        <div style={{ flex: 1, padding: "28px 32px", maxWidth: 1180 }}>
          <Active />
        </div>
      </div>
    </div>
    </LiveContext.Provider>
  );
}
