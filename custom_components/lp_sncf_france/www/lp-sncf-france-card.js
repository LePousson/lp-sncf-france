/*
 * LP SNCF France — station board card
 * Served and auto-registered by the lp_sncf_france integration.
 *
 * Styling follows a "per-role" logic: every visual setting (font, size, colour)
 * is set per element role in `styles:`; an empty value falls back to the default.
 */

const CARD_VERSION = "0.2.0";
const DOMAIN = "lp_sncf_france";

const I18N = {
  fr: {
    departures: "Départs", arrivals: "Arrivées", time: "Heure", train: "Train",
    destination: "Destination", origin: "Provenance", platform: "Voie",
    cancelled: "Supprimé", on_time: "À l'heure", scheduled: "Théorique",
    delayed: (n) => `+${n} min`, via: "Via", no_train: "Aucun train sur la période",
    assist_open: (t) => `Assistance ouverte${t ? " → " + t : ""}`,
    assist_closed: (t) => `Assistance fermée${t ? " · ouvre " + t : ""}`,
    assist_mobile: "Assistance : équipe mobile", assist_none: "Pas d'assistance",
    assist_unknown: "Assistance inconnue",
    lifts_ok: (n) => `Ascenseurs OK (${n})`, lifts_ko: (n) => `${n} ascenseur${n > 1 ? "s" : ""} en panne`,
    lifts_none: "Pas d'ascenseur recensé",
    pmr_here: "Assistance ici", pmr_term: "Assistance au terminus",
    pmr: { open: "ouverte", closed: "fermée", mobile: "équipe mobile", none: "pas de service", unknown: "inconnue" },
    rt_on: "Temps réel", rt_off: "Temps réel indisponible", meeting: "Rendez-vous",
    data: "Données SNCF Open Data — ODbL", updated: "maj",
    pick_device: "Choisis une gare LP SNCF France dans l'éditeur de la carte.",
    not_found: "Entités de la gare introuvables.",
  },
  en: {
    departures: "Departures", arrivals: "Arrivals", time: "Time", train: "Train",
    destination: "Destination", origin: "From", platform: "Plat.",
    cancelled: "Cancelled", on_time: "On time", scheduled: "Scheduled",
    delayed: (n) => `+${n} min`, via: "Via", no_train: "No train in this period",
    assist_open: (t) => `Assistance open${t ? " → " + t : ""}`,
    assist_closed: (t) => `Assistance closed${t ? " · opens " + t : ""}`,
    assist_mobile: "Assistance: mobile team", assist_none: "No assistance",
    assist_unknown: "Assistance unknown",
    lifts_ok: (n) => `Lifts OK (${n})`, lifts_ko: (n) => `${n} lift${n > 1 ? "s" : ""} out of order`,
    lifts_none: "No lift listed",
    pmr_here: "Assistance here", pmr_term: "Assistance at terminus",
    pmr: { open: "open", closed: "closed", mobile: "mobile team", none: "no service", unknown: "unknown" },
    rt_on: "Real time", rt_off: "Real time unavailable", meeting: "Meeting point",
    data: "SNCF Open Data — ODbL", updated: "updated",
    pick_device: "Pick an LP SNCF France station in the card editor.",
    not_found: "Station entities not found.",
  },
};

/* ---- Default styles (per role; '' in config = use these) ------------------ */
const DEFAULT_STYLES = {
  font: "Roboto, 'Segoe UI', 'Helvetica Neue', sans-serif",
  title_font: "Oswald, Roboto, sans-serif", title_size: 24, title_weight: 300, title_color: "",
  pill_font: "'Archivo Narrow', 'Roboto Condensed', sans-serif", pill_size: 12, pill_color: "",
  tab_font: "'Archivo Narrow', 'Roboto Condensed', sans-serif", tab_size: 13, tab_color: "",
  head_font: "Tuffy, Roboto, sans-serif", head_size: 11, head_color: "",
  time_font: "'Saira Condensed', 'Roboto Condensed', sans-serif", time_size: 20, time_color: "",
  train_font: "'Archivo Narrow', 'Roboto Condensed', sans-serif", train_size: 12, train_color: "",
  dest_font: "'Yanone Kaffeesatz', 'Roboto Condensed', sans-serif", dest_size: 19, dest_color: "",
  sub_font: "'Barlow Condensed', 'Roboto Condensed', sans-serif", sub_size: 13, sub_color: "",
  platform_font: "'Saira Condensed', 'Roboto Condensed', sans-serif", platform_size: 17, platform_color: "",
  bg: "linear-gradient(180deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0) 35%), #1c1c1e",
  row_a: "#1c1c1e", row_b: "#262628", border: "rgba(255,255,255,0.07)",
  text: "#f2f2f7", muted: "#8e8e93", pill_bg: "#2c2c2e",
  ok: "#34c759", warn: "#ff9f0a", bad: "#ff453a", accent: "#4fa3e0",
};

const MODE_COLORS = {
  "TGV INOUI": "#c2185b", TGV: "#c2185b", OUIGO: "#0096d6", "OUIGO Classique": "#0096d6",
  TER: "#2a9d8f", "Car TER": "#e9c46a", "Intercités": "#4f7cff", "Intercités de nuit": "#7b61ff",
  Transilien: "#6a994e", "Tram-train": "#8ab17d", Navette: "#adb5bd", Car: "#e9c46a",
};

const FONTS_URL =
  "https://fonts.googleapis.com/css2?family=Oswald:wght@300;400&family=Archivo+Narrow:wght@400;600" +
  "&family=Tuffy:wght@700&family=Saira+Condensed:wght@400;600&family=Yanone+Kaffeesatz:wght@400" +
  "&family=Barlow+Condensed:wght@400;500&display=swap";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

class LpSncfFranceCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._open = new Set();
    this._view = null;
    this._sig = "";
    this._liftsOpen = false;
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
  }

  static getConfigElement() {
    return document.createElement("lp-sncf-france-card-editor");
  }

  static getStubConfig(hass) {
    const ent = Object.values(hass.entities || {}).find((e) => e.platform === DOMAIN && e.device_id);
    return { device: ent ? ent.device_id : "", view: "both", rows: 10 };
  }

  setConfig(config) {
    this._config = { view: "both", rows: 10, show_header: true, show_via: true, show_platform: true,
      show_pmr: true, show_lifts: true, show_footer: true, messages: "all", load_fonts: false, ...config };
    if (!this._view) this._view = this._config.view === "arrivals" ? "arrivals" : "departures";
    if (this._config.view !== "both") this._view = this._config.view;
    if (this._config.load_fonts && !document.getElementById("lp-sncf-fonts")) {
      const l = document.createElement("link");
      l.id = "lp-sncf-fonts"; l.rel = "stylesheet"; l.href = FONTS_URL;
      document.head.appendChild(l);
    }
    this._sig = "";
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const ents = this._entities();
    const sig = [hass.language, ...Object.values(ents).map((id) => id && hass.states[id] ? hass.states[id].last_updated : "")].join("|");
    if (sig !== this._sig) { this._sig = sig; this._render(); }
  }

  getCardSize() { return 2 + Math.min(this._config?.rows || 10, 15); }
  getGridOptions() { return { columns: 12, min_columns: 6, rows: "auto" }; }

  /* ---- helpers ---- */
  _t() { return (this._hass?.language || "fr").startsWith("fr") ? I18N.fr : I18N.en; }
  _s(k) { const v = (this._config.styles || {})[k]; return v === "" || v === undefined || v === null ? DEFAULT_STYLES[k] : v; }
  _font(role) { return this._s(`${role}_font`) || this._s("font"); }
  _color(role, fallback) { const v = (this._config.styles || {})[`${role}_color`]; return v ? v : fallback; }

  _entities() {
    const out = { departures: null, arrivals: null, assistance: null, lifts: null, realtime: null };
    const hass = this._hass, dev = this._config?.device;
    if (!hass || !dev) return out;
    for (const e of Object.values(hass.entities || {})) {
      if (e.platform !== DOMAIN || e.device_id !== dev) continue;
      const st = hass.states[e.entity_id];
      if (!st) continue;
      const a = st.attributes;
      if (a.direction === "departures") out.departures = e.entity_id;
      else if (a.direction === "arrivals") out.arrivals = e.entity_id;
      else if ("meeting_point" in a || "today" in a) out.assistance = e.entity_id;
      else if ("equipment" in a) out.lifts = e.entity_id;
      else if (e.entity_id.startsWith("binary_sensor.") && "timetable_version" in a) out.realtime = e.entity_id;
    }
    return out;
  }

  _hm(iso) {
    if (!iso) return "";
    return new Date(iso).toLocaleTimeString(this._hass.language || "fr", { hour: "2-digit", minute: "2-digit" });
  }

  _dayLabel(iso) {
    const d = new Date(iso), now = new Date();
    if (d.toDateString() === now.toDateString()) return "";
    return d.toLocaleDateString(this._hass.language || "fr", { weekday: "short", day: "numeric" });
  }

  _onClick(ev) {
    const el = ev.target.closest("[data-act]");
    if (!el) return;
    const act = el.dataset.act;
    if (act === "tab") { this._view = el.dataset.view; this._render(); }
    else if (act === "row") { const id = el.dataset.id; this._open.has(id) ? this._open.delete(id) : this._open.add(id); this._render(); }
    else if (act === "lifts") { this._liftsOpen = !this._liftsOpen; this._render(); }
    else if (act === "more") {
      const ev2 = new Event("hass-more-info", { bubbles: true, composed: true });
      ev2.detail = { entityId: el.dataset.entity };
      this.dispatchEvent(ev2);
    }
  }

  /* ---- render ---- */
  _render() {
    if (!this._config || !this._hass) return;
    const T = this._t(), c = this._config, S = (k) => this._s(k);
    const ents = this._entities();
    let body = "";

    if (!c.device) body = `<div class="empty">${T.pick_device}</div>`;
    else if (!ents.departures && !ents.arrivals) body = `<div class="empty">${T.not_found}</div>`;
    else body = this._header(ents, T) + this._board(ents, T) + this._footer(ents, T);

    this.shadowRoot.innerHTML = `<style>${this._css()}</style><ha-card>${body}</ha-card>`;
  }

  _header(ents, T) {
    const c = this._config, hass = this._hass;
    if (!c.show_header) return this._tabs(T);
    const dep = hass.states[ents.departures || ents.arrivals];
    const devName = c.title || (hass.devices?.[c.device]?.name_by_user || hass.devices?.[c.device]?.name) ||
      (dep?.attributes.friendly_name || "").split(" ").slice(0, -2).join(" ");
    const pills = [];

    const as = ents.assistance && hass.states[ents.assistance];
    if (as) {
      const st = as.state, a = as.attributes;
      let txt, col;
      if (st === "open") { txt = T.assist_open(a.until); col = this._s("ok"); }
      else if (st === "closed") { txt = T.assist_closed(a.opens ? this._opensLabel(a.opens) : ""); col = this._s("bad"); }
      else if (st === "mobile") { txt = T.assist_mobile; col = this._s("warn"); }
      else if (st === "none") { txt = T.assist_none; col = this._s("muted"); }
      else { txt = T.assist_unknown; col = this._s("muted"); }
      const tip = a.meeting_point ? `${T.meeting} : ${a.meeting_point}` : "";
      pills.push(`<span class="pill" title="${esc(tip)}" data-act="more" data-entity="${ents.assistance}">
        <ha-icon icon="mdi:human-wheelchair" style="color:${col}"></ha-icon>${esc(txt)}</span>`);
    }
    if (c.show_lifts && ents.lifts && hass.states[ents.lifts]) {
      const l = hass.states[ents.lifts], ko = Number(l.state) || 0, total = l.attributes.total || 0;
      const col = ko ? this._s("bad") : total ? this._s("ok") : this._s("muted");
      const txt = total ? (ko ? T.lifts_ko(ko) : T.lifts_ok(total)) : T.lifts_none;
      pills.push(`<span class="pill" data-act="lifts"><span class="dot" style="background:${col};box-shadow:0 0 8px ${col}88"></span>${esc(txt)}</span>`);
    }
    const rt = ents.realtime && hass.states[ents.realtime];
    if (rt) {
      const on = rt.state === "on", col = on ? this._s("ok") : this._s("muted");
      pills.push(`<span class="pill" title="${on ? T.rt_on : T.rt_off}"><span class="dot ${on ? "pulse" : ""}" style="background:${col};box-shadow:0 0 8px ${col}88"></span>${on ? T.rt_on : T.rt_off}</span>`);
    }

    let lifts = "";
    if (this._liftsOpen && ents.lifts && hass.states[ents.lifts]) {
      const eq = hass.states[ents.lifts].attributes.equipment || [];
      lifts = `<div class="lifts">${eq.map((e) => {
        const col = e.state === "ok" ? this._s("ok") : e.state === "ko" ? this._s("bad") : this._s("muted");
        return `<div class="lift"><span class="dot" style="background:${col};box-shadow:0 0 8px ${col}88"></span>
          <span class="lift-name">${esc(e.name)}</span><span class="sub">${esc(e.location)}</span></div>`;
      }).join("")}</div>`;
    }
    return `<div class="head">
        <div class="title">${esc(devName)}</div>
        ${this._tabs(T)}
      </div>
      <div class="pills">${pills.join("")}</div>${lifts}`;
  }

  _opensLabel(iso) {
    const d = this._dayLabel(iso);
    return (d ? d + " " : "") + this._hm(iso);
  }

  _tabs(T) {
    if (this._config.view !== "both") return "";
    return `<div class="tabs">${["departures", "arrivals"].map((v) =>
      `<span class="tab ${this._view === v ? "on" : ""}" data-act="tab" data-view="${v}">${T[v]}</span>`).join("")}</div>`;
  }

  _board(ents, T) {
    const c = this._config, hass = this._hass;
    const eid = this._view === "arrivals" ? ents.arrivals : ents.departures;
    const st = eid && hass.states[eid];
    const rows = (st?.attributes.rows || []).slice(0, c.rows || 10);
    const isDep = this._view !== "arrivals";
    const cols = this._cols();
    let html = `<div class="row headrow" style="grid-template-columns:${cols}">
      <span>${T.time}</span><span>${T.train}</span><span>${isDep ? T.destination : T.origin}</span>
      ${c.show_platform ? `<span class="c">${T.platform}</span>` : ""}${c.show_pmr ? `<span class="c"><ha-icon class="hicon" icon="mdi:human-wheelchair"></ha-icon></span>` : ""}</div>`;
    if (!rows.length) return html + `<div class="empty">${T.no_train}</div>`;

    rows.forEach((r, i) => {
      const open = this._open.has(r.id);
      const msgs = this._msgs(r);
      const mc = MODE_COLORS[r.mode] || this._s("accent");
      const sched = this._hm(r.scheduled), exp = this._hm(r.expected), day = this._dayLabel(r.scheduled);
      let time;
      if (r.status === "cancelled") {
        time = `<span class="t strike">${sched}</span><span class="st" style="color:${this._s("bad")}">${T.cancelled}</span>`;
      } else if (r.status === "delayed") {
        time = `<span class="t" style="color:${this._s("warn")}">${exp}</span><span class="st"><s>${sched}</s> ${T.delayed(r.delay)}</span>`;
      } else {
        const col = r.status === "on_time" ? this._color("time", this._s("text")) : this._s("muted");
        time = `<span class="t" style="color:${col}">${sched}</span>${r.status === "scheduled" ? `<span class="st">${T.scheduled}</span>` : ""}`;
      }
      if (day) time = `<span class="st">${esc(day)}</span>` + time;
      const via = c.show_via && r.via?.length ? `<div class="sub via">${T.via} ${esc(r.via.slice(0, 4).join(" · "))}${r.via.length > 4 ? " …" : ""}</div>` : "";
      const warn = msgs.length ? `<ha-icon class="warn" icon="mdi:alert-circle-outline" style="color:${this._s("warn")}"></ha-icon>` : "";
      const pmr = c.show_pmr ? `<span class="c pmr">${this._pmrIcon(r.assistance_here, T.pmr_here, T)}${this._pmrIcon(r.assistance_terminus, T.pmr_term, T)}</span>` : "";
      const plat = c.show_platform ? `<span class="c plat">${r.platform ? `<span class="platbox">${esc(r.platform)}</span>` : "—"}</span>` : "";
      html += `<div class="row ${i % 2 ? "b" : "a"} ${r.status === "cancelled" ? "cancel" : ""}" style="grid-template-columns:${cols}" data-act="row" data-id="${esc(r.id)}">
        <span class="time">${time}</span>
        <span class="train"><span class="badge" style="background:${mc}1f;border-color:${mc}55;color:${mc}">${esc(r.mode)}</span><span class="num">${esc(r.train)}</span></span>
        <span class="dest"><div class="dname">${esc(r.terminus)} ${warn}</div>${via}</span>
        ${plat}${pmr}
      </div>`;
      if (open) html += this._details(r, msgs, T, i);
    });
    return html;
  }

  _cols() {
    const c = this._config;
    return ["76px", "92px", "minmax(0,1fr)", c.show_platform ? "44px" : "", c.show_pmr ? "48px" : ""].filter(Boolean).join(" ");
  }

  _msgs(r) {
    const mode = this._config.messages;
    if (mode === "none") return [];
    const minor = ["slight", "noImpact", "verySlight", "unknown", ""];
    return (r.messages || []).filter((m) => mode !== "major" || !minor.includes(m.severity));
  }

  _pmrIcon(state, label, T) {
    const col = state === "open" ? this._s("ok") : state === "closed" ? this._s("bad") : state === "mobile" ? this._s("warn") : this._s("muted");
    return `<ha-icon icon="mdi:human-wheelchair" title="${esc(label)} : ${esc(T.pmr[state] || state)}" style="color:${col}"></ha-icon>`;
  }

  _details(r, msgs, T, i) {
    const via = r.via?.length ? `<div class="sub"><b>${T.via}</b> ${esc(r.via.join(" · "))}</div>` : "";
    const line = r.line ? `<div class="sub">${esc(r.line)}</div>` : "";
    const pc = (st) => st === "open" ? this._s("ok") : st === "closed" ? this._s("bad") : st === "mobile" ? this._s("warn") : this._s("muted");
    const pmr = `<div class="sub pmrline"><ha-icon icon="mdi:human-wheelchair"></ha-icon>
      ${T.pmr_here} : <b style="color:${pc(r.assistance_here)}">${esc(T.pmr[r.assistance_here] || "")}</b> ·
      ${T.pmr_term} : <b style="color:${pc(r.assistance_terminus)}">${esc(T.pmr[r.assistance_terminus] || "")}</b></div>`;
    const m = msgs.map((x) => `<div class="msg"><ha-icon icon="mdi:alert-circle-outline" style="color:${this._s("warn")}"></ha-icon>
      <div><div class="msg-t">${esc(x.summary)}</div>${x.text && x.text !== x.summary ? `<div class="sub">${esc(x.text)}</div>` : ""}</div></div>`).join("");
    return `<div class="details ${i % 2 ? "b" : "a"}">${line}${via}${pmr}${m}</div>`;
  }

  _footer(ents, T) {
    if (!this._config.show_footer) return "";
    const st = this._hass.states[ents.departures || ents.arrivals];
    const up = st?.attributes.realtime?.updated;
    return `<div class="foot">${T.data}${up ? ` · ${T.updated} ${this._hm(up)}` : ""}</div>`;
  }

  _css() {
    const S = (k) => this._s(k), F = (r) => this._font(r);
    const C = (r, d) => this._color(r, d);
    return `
      ha-card { background:${S("bg")}; color:${S("text")}; font-family:${S("font")}; overflow:hidden;
        border-radius:var(--ha-card-border-radius,18px); border:1px solid ${S("border")}; box-shadow:0 8px 24px rgba(0,0,0,.45); padding:0 }
      .head { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:14px 16px 6px }
      .title { font-family:${F("title")}; font-size:${S("title_size")}px; font-weight:${S("title_weight")}; color:${C("title", S("text"))};
        white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
      .tabs { display:flex; gap:4px; background:${S("pill_bg")}; border-radius:999px; padding:3px; box-shadow:inset 0 1px 0 rgba(255,255,255,.08); flex-shrink:0 }
      .tab { font-family:${F("tab")}; font-size:${S("tab_size")}px; color:${C("tab", S("muted"))}; padding:4px 12px; border-radius:999px; cursor:pointer; user-select:none }
      .tab.on { background:${S("accent")}26; color:${S("accent")} }
      .pills { display:flex; flex-wrap:wrap; gap:6px; padding:4px 16px 10px }
      .pill { display:inline-flex; align-items:center; gap:6px; font-family:${F("pill")}; font-size:${S("pill_size")}px; color:${C("pill", S("text"))};
        background:${S("pill_bg")}; border-radius:999px; padding:4px 10px; box-shadow:inset 0 1px 0 rgba(255,255,255,.08); cursor:pointer }
      .pill ha-icon { --mdc-icon-size:16px }
      .dot { width:9px; height:9px; border-radius:50%; display:inline-block; flex-shrink:0 }
      .pulse { animation:pulse 2s infinite }
      @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:.35 } }
      .lifts { padding:0 16px 10px; display:grid; gap:4px }
      .lift { display:flex; align-items:center; gap:8px; font-family:${F("pill")}; font-size:${S("pill_size")}px }
      .lift .sub { margin-left:auto }
      .row { display:grid; align-items:center; gap:8px; padding:7px 16px; cursor:pointer }
      .row.a { background:${S("row_a")} } .row.b { background:${S("row_b")} }
      .row.cancel .dname, .row.cancel .num { opacity:.55; text-decoration:line-through }
      .headrow { cursor:default; font-family:${F("head")}; font-size:${S("head_size")}px; font-weight:700; text-transform:uppercase;
        letter-spacing:1.5px; color:${C("head", S("muted"))}; padding-top:6px; padding-bottom:6px; border-top:1px solid ${S("border")} }
      .c { text-align:center; justify-self:center }
      .hicon { --mdc-icon-size:15px; color:${C("head", S("muted"))} }
      .pmrline { display:flex; align-items:center; gap:4px; flex-wrap:wrap } .pmrline ha-icon { --mdc-icon-size:15px }
      .time { display:flex; flex-direction:column; line-height:1.05 }
      .t { font-family:${F("time")}; font-size:${S("time_size")}px; font-weight:600; color:${C("time", S("text"))} }
      .t.strike { text-decoration:line-through; color:${S("muted")} }
      .st { font-family:${F("sub")}; font-size:${S("sub_size") - 1}px; color:${C("sub", S("muted"))} }
      .train { display:flex; flex-direction:column; align-items:flex-start; gap:3px; min-width:0 }
      .badge { font-family:${F("train")}; font-size:${S("train_size") - 1}px; font-weight:600; border:1px solid; border-radius:6px; padding:1px 6px;
        white-space:nowrap; max-width:100%; overflow:hidden; text-overflow:ellipsis }
      .num { font-family:${F("train")}; font-size:${S("train_size")}px; color:${C("train", S("muted"))} }
      .dest { min-width:0 }
      .dname { font-family:${F("dest")}; font-size:${S("dest_size")}px; color:${C("dest", S("text"))}; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
        display:flex; align-items:center; gap:6px }
      .dname ha-icon { --mdc-icon-size:16px; flex-shrink:0 }
      .sub { font-family:${F("sub")}; font-size:${S("sub_size")}px; color:${C("sub", S("muted"))} }
      .via { white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
      .platbox { font-family:${F("platform")}; font-size:${S("platform_size")}px; font-weight:600; color:${C("platform", S("text"))};
        border:1px solid ${S("border")}; background:${S("pill_bg")}; border-radius:6px; min-width:26px; display:inline-block; padding:0 4px }
      .plat { color:${S("muted")} }
      .pmr { display:flex; gap:1px } .pmr ha-icon { --mdc-icon-size:17px }
      .details { padding:4px 16px 10px 100px; display:grid; gap:4px; border-left:3px solid ${S("accent")} }
      .details.a { background:${S("row_a")} } .details.b { background:${S("row_b")} }
      .msg { display:flex; gap:8px; align-items:flex-start } .msg ha-icon { --mdc-icon-size:18px; flex-shrink:0 }
      .msg-t { font-family:${F("pill")}; font-size:${S("pill_size") + 1}px; color:${S("text")} }
      .empty { padding:16px; color:${S("muted")}; font-family:${F("sub")}; font-size:${S("sub_size") + 1}px }
      .foot { padding:8px 16px 10px; font-family:${F("sub")}; font-size:${S("sub_size") - 2}px; color:${S("muted")}; border-top:1px solid ${S("border")} }
      @media (max-width: 420px) { .details { padding-left:16px } }
    `;
  }
}

/* ---------------------------------------------------------------------------
 * Visual editor (ha-form)
 * ------------------------------------------------------------------------- */
const ROLES = ["title", "pill", "tab", "head", "time", "train", "dest", "sub", "platform"];

const LABELS = {
  fr: {
    device: "Gare", title: "Titre (vide = nom de la gare)", view: "Affichage", rows: "Nombre de lignes",
    show_header: "En-tête", show_via: "Dessertes", show_platform: "Voie", show_pmr: "Pastilles PMR",
    show_lifts: "Ascenseurs", show_footer: "Pied de carte", messages: "Messages d'incident",
    load_fonts: "Charger les polices (Google Fonts)", styles: "Polices & couleurs (vide = défaut)",
    font: "Police générale", bg: "Fond", row_a: "Ligne A", row_b: "Ligne B", border: "Bordure",
    text: "Texte", muted: "Texte secondaire", pill_bg: "Fond des pastilles", ok: "Couleur OK",
    warn: "Couleur alerte", bad: "Couleur problème", accent: "Couleur d'accent",
    role: { title: "Titre", pill: "Pastilles", tab: "Onglets", head: "En-têtes", time: "Heures", train: "Train",
      dest: "Destination", sub: "Sous-textes", platform: "Voie" },
    font_s: "police", size_s: "taille", color_s: "couleur",
    v: { both: "Départs + arrivées (onglets)", departures: "Départs", arrivals: "Arrivées" },
    m: { all: "Tous", major: "Importants seulement", none: "Aucun" },
  },
  en: {
    device: "Station", title: "Title (empty = station name)", view: "Display", rows: "Rows",
    show_header: "Header", show_via: "Calling points", show_platform: "Platform", show_pmr: "PMR badges",
    show_lifts: "Lifts", show_footer: "Footer", messages: "Disruption messages",
    load_fonts: "Load fonts (Google Fonts)", styles: "Fonts & colours (empty = default)",
    font: "General font", bg: "Background", row_a: "Row A", row_b: "Row B", border: "Border",
    text: "Text", muted: "Secondary text", pill_bg: "Pill background", ok: "OK colour",
    warn: "Warning colour", bad: "Problem colour", accent: "Accent colour",
    role: { title: "Title", pill: "Pills", tab: "Tabs", head: "Headers", time: "Times", train: "Train",
      dest: "Destination", sub: "Sub-texts", platform: "Platform" },
    font_s: "font", size_s: "size", color_s: "colour",
    v: { both: "Departures + arrivals (tabs)", departures: "Departures", arrivals: "Arrivals" },
    m: { all: "All", major: "Major only", none: "None" },
  },
};

class LpSncfFranceCardEditor extends HTMLElement {
  setConfig(config) { this._config = config; this._render(); }
  set hass(hass) { this._hass = hass; if (this._form) this._form.hass = hass; else this._render(); }

  _L() { return (this._hass?.language || "fr").startsWith("fr") ? LABELS.fr : LABELS.en; }

  _schema() {
    const L = this._L();
    const styleSchema = [{ name: "font", selector: { text: {} } }];
    for (const r of ROLES) {
      styleSchema.push({ type: "grid", name: "", schema: [
        { name: `${r}_font`, selector: { text: {} } },
        { name: `${r}_size`, selector: { number: { min: 6, max: 60, mode: "box", unit_of_measurement: "px" } } },
        { name: `${r}_color`, selector: { text: {} } },
      ] });
    }
    styleSchema.push({ type: "grid", name: "", schema: ["bg", "row_a", "row_b", "border", "text", "muted", "pill_bg", "accent", "ok", "warn", "bad"]
      .map((n) => ({ name: n, selector: { text: {} } })) });
    return [
      { name: "device", required: true, selector: { device: { integration: DOMAIN } } },
      { name: "title", selector: { text: {} } },
      { type: "grid", name: "", schema: [
        { name: "view", selector: { select: { mode: "dropdown", options: ["both", "departures", "arrivals"].map((v) => ({ value: v, label: L.v[v] })) } } },
        { name: "rows", selector: { number: { min: 1, max: 40, mode: "box" } } },
      ] },
      { name: "messages", selector: { select: { mode: "dropdown", options: ["all", "major", "none"].map((v) => ({ value: v, label: L.m[v] })) } } },
      { type: "grid", name: "", schema: ["show_header", "show_via", "show_platform", "show_pmr", "show_lifts", "show_footer", "load_fonts"]
        .map((n) => ({ name: n, selector: { boolean: {} } })) },
      { type: "expandable", name: "styles", title: L.styles, schema: styleSchema },
    ];
  }

  _label = (s) => {
    const L = this._L(), n = s.name;
    if (L[n] && typeof L[n] === "string") return L[n];
    const m = n.match(/^(\w+?)_(font|size|color)$/);
    if (m && L.role[m[1]]) return `${L.role[m[1]]} — ${L[m[2] + "_s"]}`;
    return n;
  };

  _render() {
    if (!this._config || !this._hass) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = this._label;
      this._form.addEventListener("value-changed", (ev) => {
        const config = { type: this._config.type, ...ev.detail.value };
        this._config = config;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = this._schema();
    this._form.data = { view: "both", rows: 10, show_header: true, show_via: true, show_platform: true, show_pmr: true,
      show_lifts: true, show_footer: true, messages: "all", load_fonts: false, styles: {}, ...this._config };
  }
}

customElements.define("lp-sncf-france-card", LpSncfFranceCard);
customElements.define("lp-sncf-france-card-editor", LpSncfFranceCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "lp-sncf-france-card",
  name: "LP SNCF France",
  description: "Station board: departures, arrivals, PSH/PMR assistance, lifts (SNCF open data).",
  preview: true,
  documentationURL: "https://github.com/LePousson/lp-sncf-france",
});

console.info(`%c LP-SNCF-FRANCE-CARD %c ${CARD_VERSION} `, "color:#fff;background:#c2185b;font-weight:700", "color:#c2185b;background:#1c1c1e");
