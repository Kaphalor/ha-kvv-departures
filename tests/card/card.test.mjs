// Browser test for the Lovelace card. Run: npm i --no-save playwright-core && CHROME=/path/to/chrome node tests/card/card.test.mjs
import { chromium } from "playwright-core";
import fs from "node:fs";

const ROOT = new URL("../..", import.meta.url).pathname;
const OUT = process.env.TMPDIR || "/tmp";
const data = JSON.parse(fs.readFileSync(new URL("./fixture.json", import.meta.url), "utf8"));
const js = fs.readFileSync(`${ROOT}custom_components/kvv_departures/frontend/kvv-departures-card.js`, "utf8");

const browser = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const errors = [];
let failures = 0;
const check = (name, ok, extra = "") => { console.log(`${ok ? "PASS" : "FAIL"} ${name} ${extra}`); if (!ok) failures++; };

async function run(lang, dark, shot, config, source = "efa") {
  const page = await browser.newPage({ viewport: { width: 520, height: 760 } });
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.setContent(`<!doctype html><html><head><style>
    :root { ${dark ? "--card-background-color:#1c1c1c;--primary-text-color:#e1e1e1;--secondary-text-color:#9b9b9b;--divider-color:rgba(255,255,255,.12);" :
      "--card-background-color:#fff;--primary-text-color:#212121;--secondary-text-color:#727272;--divider-color:rgba(0,0,0,.12);"}
      --primary-color:#03a9f4; }
    body { margin:0; padding:16px; background:${dark ? "#111" : "#e9ecef"}; font-family: Roboto, system-ui, sans-serif; }
    ha-card { display:block; background:var(--card-background-color); border-radius:12px; box-shadow:0 1px 3px rgba(0,0,0,.2); }
  </style></head><body></body></html>`);
  await page.addScriptTag({ content: js });
  await page.evaluate(({ data, lang, config, source }) => {
    const el = document.createElement("kvv-departures-card");
    document.body.appendChild(el);
    window.__moreInfo = [];
    el.addEventListener("hass-more-info", (e) => window.__moreInfo.push(e.detail.entityId));
    el.setConfig({ entity: "sensor.durlacher_tor_next_departure", ...config });
    el.hass = {
      language: lang, locale: { language: lang },
      states: { "sensor.durlacher_tor_next_departure": { state: data.departures[0].actual, last_updated: new Date().toISOString(),
        attributes: { stop: data.stop, source, departures: data.departures } } },
    };
    window.__el = el;
  }, { data, lang, config: config || {}, source });
  await page.waitForTimeout(150);
  return page;
}

// 1) German, board style: badge colors must equal the backend colors
let page = await run("de", true, "board_de", {});
const badges = await page.evaluate(() => [...window.__el.shadowRoot.querySelectorAll(".badge")].map((b) => ({ t: b.textContent, bg: getComputedStyle(b).backgroundColor, fg: getComputedStyle(b).color })));
const hex = (h) => { const n = parseInt(h.slice(1), 16); return `rgb(${n >> 16}, ${(n >> 8) & 255}, ${n & 255})`; };
check("one row per departure", badges.length === data.departures.length, `${badges.length}`);
check("badge colors match official colors", badges.every((b, i) => b.bg === hex(data.departures[i].color) && b.fg === hex(data.departures[i].text_color)));
check("de strings", (await page.evaluate(() => window.__el.shadowRoot.textContent)).includes("Stand"));
await page.screenshot({ path: `${OUT}/board_de.png` });

// 2) click a delayed departure -> dialog in body, with details
const idx = data.departures.findIndex((d) => d.delay >= 5);
await page.evaluate((i) => window.__el.shadowRoot.querySelectorAll(".row")[i].click(), idx);
await page.waitForTimeout(100);
const dlg = await page.evaluate(() => {
  const h = document.querySelector("[data-kvv-dialog]");
  return h ? { text: h.shadowRoot.textContent, head: getComputedStyle(h.shadowRoot.querySelector(".head")).backgroundColor } : null;
});
check("dialog opens in body", !!dlg);
check("dialog header uses line color", dlg && dlg.head === hex(data.departures[idx].color), dlg && dlg.head);
check("dialog shows delay + stop + operator", dlg && /verspätet/.test(dlg.text) && dlg.text.includes("Durlacher Tor") && dlg.text.includes("Verkehrsbetriebe"));
check("EFA: notices shown", dlg && dlg.text.includes("Hinweise") && dlg.text.includes("Bauarbeiten"));
check("platform not duplicated", dlg && !/Gleis\s*Gleis/.test(dlg.text) && /Gleis\s*4/.test(dlg.text), dlg && dlg.text.match(/Gleis.{0,12}/)?.[0]);
await page.screenshot({ path: `${OUT}/dialog_de.png` });

// 3) Escape closes dialog and returns focus; "show entity" fires hass-more-info
await page.keyboard.press("Escape");
check("Escape closes dialog", await page.evaluate(() => !document.querySelector("[data-kvv-dialog]")));
await page.evaluate(() => window.__el.shadowRoot.querySelector(".row").click());
await page.evaluate(() => document.querySelector("[data-kvv-dialog]").shadowRoot.querySelector('[data-act="entity"]').click());
check("show entity fires hass-more-info", (await page.evaluate(() => window.__moreInfo)).includes("sensor.durlacher_tor_next_departure"));
check("dialog closed after show entity", await page.evaluate(() => !document.querySelector("[data-kvv-dialog]")));
await page.close();

// 4) English, HA theme (board:false), max 4 rows, cancelled departure
page = await run("en", false, "light_en", { board: false, max_departures: 4, title: "My stop" });
check("max_departures", (await page.evaluate(() => window.__el.shadowRoot.querySelectorAll(".row").length)) === 4);
check("en strings + title", await page.evaluate(() => { const t = window.__el.shadowRoot.textContent; return t.includes("Updated") && t.includes("My stop") && t.includes("Cancelled"); }));
await page.screenshot({ path: `${OUT}/light_en.png` });
await page.close();

// 4b) TRIAS source: notices must stay hidden even if a departure carries some
page = await run("de", true, "trias", {}, "trias");
await page.evaluate((i) => window.__el.shadowRoot.querySelectorAll(".row")[i].click(), idx);
const trText = await page.evaluate(() => document.querySelector("[data-kvv-dialog]").shadowRoot.textContent);
check("TRIAS: no notices section", !trText.includes("Hinweise") && !trText.includes("Bauarbeiten"));
check("TRIAS: other details still shown", trText.includes("Betreiber") && trText.includes("Gleis"));
await page.close();

// 5) Missing entity / unavailable
page = await run("de", true, "x", { entity: "" });
check("empty entity hint", (await page.evaluate(() => window.__el.shadowRoot.textContent)).includes("Wähle den Sensor"));
await page.close();

check("no page errors", errors.length === 0, errors.join(" | "));
await browser.close();
process.exit(failures ? 1 : 0);
