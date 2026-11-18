/**
 * KVV Departures card for Home Assistant.
 * Departure board with official KVV line colors; click a departure for details.
 * Config: entity (the "Next departure" sensor), title, max_departures, board, show_platform.
 */
const CARD_VERSION = "2.1.0";

const I18N = {
  en: {
    no_departures: "No departures",
    select_entity: "Select the “Next departure” sensor of a KVV stop.",
    unavailable: "KVV data unavailable",
    updated: "Updated",
    now: "now",
    in_min: "in {n} min",
    on_time: "on time",
    delay_min: "+{n} min",
    cancelled: "Cancelled",
    platform: "Platform",
    departure: "Departure",
    planned: "planned {t}",
    status: "Status",
    status_cancelled: "Cancelled",
    status_delayed: "Delayed by {n} min",
    status_on_time: "On time (real-time)",
    status_scheduled: "Scheduled (no real-time data)",
    stop: "Stop",
    transport: "Transport",
    operator: "Operator",
    notices: "Notices",
    show_entity: "Show entity",
    close: "Close",
    modes: { tram: "Tram", sbahn: "S-Bahn", ubahn: "Underground tram", bus: "Bus", zug: "Train", seilbahn: "Cable car", schiff: "Ferry", sonstige: "Other" },
    ed_entity: "Next departure sensor",
    ed_title: "Title (optional)",
    ed_max: "Maximum departures",
    ed_board: "Departure board style (dark)",
    ed_platform: "Show platform",
  },
  de: {
    no_departures: "Keine Abfahrten",
    select_entity: "Wähle den Sensor „Nächste Abfahrt“ einer KVV-Haltestelle.",
    unavailable: "KVV-Daten nicht verfügbar",
    updated: "Stand",
    now: "jetzt",
    in_min: "in {n} Min.",
    on_time: "pünktlich",
    delay_min: "+{n} Min.",
    cancelled: "Fällt aus",
    platform: "Gleis",
    departure: "Abfahrt",
    planned: "planmäßig {t}",
    status: "Status",
    status_cancelled: "Fällt aus",
    status_delayed: "{n} Minuten verspätet",
    status_on_time: "Pünktlich (Echtzeit)",
    status_scheduled: "Planmäßig (keine Echtzeitdaten)",
    stop: "Haltestelle",
    transport: "Verkehrsmittel",
    operator: "Betreiber",
    notices: "Hinweise",
    show_entity: "Entität anzeigen",
    close: "Schließen",
    modes: { tram: "Straßenbahn", sbahn: "S-Bahn", ubahn: "Stadtbahn (unterirdisch)", bus: "Bus", zug: "Zug", seilbahn: "Seilbahn", schiff: "Fähre", sonstige: "Sonstige" },
    ed_entity: "Sensor „Nächste Abfahrt“",
    ed_title: "Titel (optional)",
    ed_max: "Maximale Anzahl Abfahrten",
    ed_board: "Abfahrtstafel-Stil (dunkel)",
    ed_platform: "Gleis anzeigen",
  },
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeColor = (c, fallback) => (/^#[0-9a-f]{6}$/i.test(c || "") ? c : fallback);
const fmt = (s, vars = {}) => String(s).replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");

function strings(hass) {
  const lang = ((hass && ((hass.locale && hass.locale.language) || hass.language)) || "en").split("-")[0];
  return { lang, t: I18N[lang] || I18N.en };
}

/** Delay presentation shared by the board and the dialog. */
function delayInfo(d, t) {
  if (d.cancelled) return { cls: "bad", text: t.cancelled };
  if (!d.realtime || d.delay == null) return { cls: "", text: "" };
  if (d.delay <= 0) return { cls: "ok", text: t.on_time };
  return { cls: d.delay >= 5 ? "bad" : "warn", text: fmt(t.delay_min, { n: d.delay }) };
}

function countdown(d, t) {
  const m = Math.round((new Date(d.actual).getTime() - Date.now()) / 60000);
  if (Number.isNaN(m)) return "";
  return m <= 0 ? t.now : fmt(t.in_min, { n: m });
}

const CARD_STYLE = `
  :host { display: block; }
  ha-card { overflow: hidden; }
  .wrap {
    --bg: var(--ha-card-background, var(--card-background-color, #fff));
    --fg: var(--primary-text-color, #212121); --muted: var(--secondary-text-color, #727272);
    --time: var(--primary-text-color, #212121); --line: var(--divider-color, rgba(127,127,127,.3));
    --ok: var(--success-color, #2e7d32); --warn: #b45309; --bad: var(--error-color, #c62828);
    --head: transparent;
    background: var(--bg); color: var(--fg);
  }
  .wrap.board {
    --bg: #0d1b2e; --fg: #f4f7fb; --muted: #9fb0c6; --time: #ffd34d; --line: rgba(255,255,255,.12);
    --ok: #6ee7a0; --warn: #ffb454; --bad: #ff7b7b; --head: #13294a;
  }
  header { display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
           padding: 12px 16px; background: var(--head); }
  .wrap.board header { border-bottom: 2px solid #ffd34d; }
  .title { font-size: 1.15em; font-weight: 600; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .upd { color: var(--muted); font-size: .8em; white-space: nowrap; font-variant-numeric: tabular-nums; }
  .row { all: unset; box-sizing: border-box; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 12px;
         align-items: center; width: 100%; padding: 10px 16px; cursor: pointer; border-top: 1px solid var(--line); }
  .row:first-of-type { border-top: 0; }
  .row:hover { background: rgba(127,127,127,.12); }
  .row:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: -2px; }
  .badge { min-width: 3.4em; padding: 4px 8px; text-align: center; font-weight: 700; font-size: 1.05em; border-radius: 6px;
           box-shadow: 0 0 0 1px rgba(255,255,255,.2); white-space: nowrap; }
  .dir { font-weight: 600; font-size: 1.05em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sub { color: var(--muted); font-size: .8em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .cx .dir, .cx .t { text-decoration: line-through; opacity: .6; }
  .time { text-align: right; font-variant-numeric: tabular-nums; }
  .t { font-size: 1.35em; font-weight: 700; color: var(--time); line-height: 1.15; }
  .d { font-size: .8em; font-weight: 600; }
  .d.ok { color: var(--ok); } .d.warn { color: var(--warn); } .d.bad { color: var(--bad); }
  .planned { color: var(--muted); font-size: .75em; text-decoration: line-through; margin-right: 6px; font-weight: 400; }
  .empty { padding: 18px 16px; color: var(--muted); }
`;

class KvvDeparturesCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._sig = null;
    this._tick = null;
    this._dialog = null;
    this.shadowRoot.addEventListener("click", (e) => {
      const row = e.target.closest(".row");
      if (row && this._deps) this._openDialog(this._deps[Number(row.dataset.i)], row);
    });
  }

  static getConfigElement() { return document.createElement("kvv-departures-card-editor"); }

  static getStubConfig(hass) {
    const found = Object.keys((hass && hass.states) || {}).find(
      (id) => id.startsWith("sensor.") && Array.isArray(hass.states[id].attributes.departures));
    return { entity: found || "", board: true };
  }

  setConfig(config) {
    this._config = { board: true, show_platform: true, ...config };
    this._sig = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 1 + Math.min((this._deps || []).length || 4, (this._config && this._config.max_departures) || 20); }
  getGridOptions() { return { columns: 12, min_columns: 6 }; }

  connectedCallback() {
    this._tick = setInterval(() => this._render(), 30000);
  }
  disconnectedCallback() {
    clearInterval(this._tick);
    this._closeDialog(false);
  }

  _render() {
    const c = this._config, hass = this._hass;
    if (!c || !hass) return;
    const st = c.entity ? hass.states[c.entity] : undefined;
    const { lang, t } = strings(hass);
    // Re-render when the entity changed, the language/config changed, or 30 s passed (countdowns)
    const sig = [st && st.last_updated, st && st.state, lang, JSON.stringify(c), Math.floor(Date.now() / 30000)].join("|");
    if (sig === this._sig) return;
    this._sig = sig;

    let body;
    this._deps = [];
    if (!c.entity) {
      body = `<div class="empty">${esc(t.select_entity)}</div>`;
    } else if (!st || st.state === "unavailable") {
      body = `<div class="empty">${esc(t.unavailable)}</div>`;
    } else {
      const all = Array.isArray(st.attributes.departures) ? st.attributes.departures : [];
      this._deps = all.slice(0, c.max_departures > 0 ? c.max_departures : all.length);
      body = this._deps.length ? this._deps.map((d, i) => this._row(d, i, t)).join("")
                               : `<div class="empty">${esc(t.no_departures)}</div>`;
    }

    const title = c.title || (st && st.attributes.stop) || "";
    const upd = st ? new Date(st.last_updated).toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" }) : "";
    this.shadowRoot.innerHTML = `<style>${CARD_STYLE}</style>
      <ha-card><div class="wrap ${c.board === false ? "" : "board"}">
        <header><span class="title">${esc(title)}</span><span class="upd">${upd ? `${esc(t.updated)} ${esc(upd)}` : ""}</span></header>
        ${body}
      </div></ha-card>`;
  }

  _row(d, i, t) {
    const bg = safeColor(d.color, "#5b6573"), fg = safeColor(d.text_color, "#ffffff");
    const di = delayInfo(d, t);
    const late = d.realtime && d.delay > 0 && !d.cancelled;
    const sub = [this._config.show_platform !== false && d.platform ? d.platform : "", d.cancelled ? "" : countdown(d, t)].filter(Boolean).join(" · ");
    const label = `${d.line} ${d.direction}, ${d.time}${di.text ? ", " + di.text : ""}`;
    return `<button class="row ${d.cancelled ? "cx" : ""}" data-i="${i}" aria-haspopup="dialog" aria-label="${esc(label)}">
      <span class="badge" style="background:${bg};color:${fg}">${esc(d.line)}</span>
      <span><div class="dir">${esc(d.direction)}</div><div class="sub">${esc(sub)}</div></span>
      <span class="time"><div class="t">${late ? `<span class="planned">${esc(d.planned_time)}</span>` : ""}${esc(d.time)}</div>
        <div class="d ${di.cls}">${esc(di.text)}</div></span></button>`;
  }

  // ---------------------------------------------------------------- dialog
  _openDialog(d, trigger) {
    if (!d) return;
    this._closeDialog(false);
    const { t } = strings(this._hass);
    const bg = safeColor(d.color, "#5b6573"), fg = safeColor(d.text_color, "#ffffff");
    const di = delayInfo(d, t);
    const late = d.realtime && d.delay > 0 && !d.cancelled;
    const status = d.cancelled ? t.status_cancelled
      : !d.realtime ? t.status_scheduled
      : d.delay > 0 ? fmt(t.status_delayed, { n: d.delay }) : t.status_on_time;
    const rows = [
      [t.departure, `<b>${esc(d.time)}</b>${late ? ` <span class="muted">(${esc(fmt(t.planned, { t: d.planned_time }))})</span>` : ""}`],
      [t.status, `<span class="chip ${di.cls}">${esc(status)}</span>`],
      d.platform && [t.platform, esc(d.platform)],
      d.stop && [t.stop, esc(d.stop)],
      [t.transport, esc((t.modes[d.mode]) || t.modes.sonstige)],
      d.operator && [t.operator, esc(d.operator)],
    ].filter(Boolean);
    const notices = (d.infos || []).map((n) => {
      const link = /^https?:\/\//i.test(n.url || "") ? `<a href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">${esc(n.title)}</a>` : esc(n.title);
      return `<li>${link}</li>`;
    }).join("");

    const host = document.createElement("div");
    host.setAttribute("data-kvv-dialog", "");
    const root = host.attachShadow({ mode: "open" });
    root.innerHTML = `<style>
      .scrim { position: fixed; inset: 0; z-index: 10000; background: rgba(0,0,0,.55); display: flex; align-items: center; justify-content: center; padding: 16px; }
      .dlg { width: min(440px, 100%); max-height: 100%; overflow: auto; border-radius: 16px; font-family: var(--paper-font-body1_-_font-family, Roboto, system-ui, sans-serif);
             background: var(--card-background-color, #fff); color: var(--primary-text-color, #212121); box-shadow: 0 12px 40px rgba(0,0,0,.4); }
      .head { display: flex; align-items: center; gap: 14px; padding: 18px 20px; background: ${bg}; color: ${fg}; }
      .head .num { font-size: 2em; font-weight: 800; line-height: 1; min-width: 1.6em; }
      .head .to { font-size: 1.1em; font-weight: 600; }
      .head .from { opacity: .85; font-size: .85em; }
      dl { margin: 0; padding: 8px 20px; display: grid; grid-template-columns: max-content 1fr; gap: 10px 16px; }
      dt { color: var(--secondary-text-color, #727272); }
      dd { margin: 0; }
      .muted { color: var(--secondary-text-color, #727272); }
      .chip { display: inline-block; padding: 1px 10px; border-radius: 999px; font-size: .9em; font-weight: 500; background: rgba(127,127,127,.18); }
      .chip.ok { background: rgba(46,125,50,.18); color: var(--success-color, #2e7d32); }
      .chip.warn { background: rgba(245,158,11,.2); color: #b45309; }
      .chip.bad { background: rgba(198,40,40,.16); color: var(--error-color, #c62828); }
      h3 { margin: 6px 20px 0; font-size: .95em; font-weight: 500; color: var(--secondary-text-color, #727272); }
      ul { margin: 4px 20px 8px; padding-left: 18px; } li { margin: 4px 0; }
      a { color: var(--primary-color, #03a9f4); }
      .foot { display: flex; justify-content: flex-end; gap: 8px; padding: 10px 14px 14px; }
      button { font: inherit; font-weight: 500; border: 0; background: transparent; color: var(--primary-color, #03a9f4); border-radius: 18px; padding: 8px 14px; cursor: pointer; }
      button:hover { background: rgba(127,127,127,.15); }
      button:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); }
    </style>
    <div class="scrim"><div class="dlg" role="dialog" aria-modal="true" aria-labelledby="ttl">
      <div class="head"><span class="num">${esc(d.line)}</span>
        <span><div class="to" id="ttl">${esc(d.direction)}</div></span></div>
      <dl>${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join("")}</dl>
      ${notices ? `<h3>${esc(t.notices)}</h3><ul>${notices}</ul>` : ""}
      <div class="foot"><button data-act="entity">${esc(t.show_entity)}</button><button data-act="close">${esc(t.close)}</button></div>
    </div></div>`;

    root.addEventListener("click", (e) => {
      const act = e.target.closest("[data-act]");
      if (e.target.classList.contains("scrim") || (act && act.dataset.act === "close")) this._closeDialog(true);
      else if (act && act.dataset.act === "entity") {
        this._closeDialog(false);
        this.dispatchEvent(new CustomEvent("hass-more-info", { bubbles: true, composed: true, detail: { entityId: this._config.entity } }));
      }
    });
    this._onKey = (e) => { if (e.key === "Escape") this._closeDialog(true); };
    document.addEventListener("keydown", this._onKey);
    document.body.appendChild(host);
    this._dialog = { host, trigger };
    const first = root.querySelector('[data-act="close"]');
    if (first) first.focus();
  }

  _closeDialog(restoreFocus) {
    if (!this._dialog) return;
    document.removeEventListener("keydown", this._onKey);
    this._dialog.host.remove();
    if (restoreFocus && this._dialog.trigger && this._dialog.trigger.isConnected) this._dialog.trigger.focus();
    this._dialog = null;
  }
}

class KvvDeparturesCardEditor extends HTMLElement {
  setConfig(config) { this._config = config; this._render(); }
  set hass(hass) { this._hass = hass; if (this._form) this._form.hass = hass; this._render(); }

  _render() {
    if (!this._config || !this._hass) return;
    const { t } = strings(this._hass);
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (e) => {
        this._config = e.detail.value;
        this.dispatchEvent(new CustomEvent("config-changed", { bubbles: true, composed: true, detail: { config: this._config } }));
      });
      this.appendChild(this._form);
    }
    const labels = { entity: t.ed_entity, title: t.ed_title, max_departures: t.ed_max, board: t.ed_board, show_platform: t.ed_platform };
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = [
      { name: "entity", required: true, selector: { entity: { domain: "sensor", integration: "kvv_departures", device_class: "timestamp" } } },
      { name: "title", selector: { text: {} } },
      { name: "max_departures", selector: { number: { min: 1, max: 20, mode: "box" } } },
      { name: "board", selector: { boolean: {} } },
      { name: "show_platform", selector: { boolean: {} } },
    ];
    this._form.computeLabel = (s) => labels[s.name] || s.name;
  }
}

if (!customElements.get("kvv-departures-card")) customElements.define("kvv-departures-card", KvvDeparturesCard);
if (!customElements.get("kvv-departures-card-editor")) customElements.define("kvv-departures-card-editor", KvvDeparturesCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "kvv-departures-card")) {
  window.customCards.push({
    type: "kvv-departures-card",
    name: "KVV Departures",
    description: "Departure board with official KVV line colors and delays.",
    preview: false,
    documentationURL: "https://github.com/Kaphalor/ha-kvv-departures",
  });
}
console.info(`%c KVV-DEPARTURES-CARD %c ${CARD_VERSION} `, "background:#e30613;color:#fff;font-weight:700", "background:#333;color:#fff");
