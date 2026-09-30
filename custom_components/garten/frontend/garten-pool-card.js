/*
 * Garten – Pool card for Home Assistant.
 *
 * Bound to the "water quality" sensor of a Garten pool. That sensor carries
 * the entity ids of everything else (card_entities / card_sources), so the
 * card needs no further configuration.
 *
 *   type: custom:garten-pool-card
 *   entity: sensor.pool_wasserqualitat
 *   show_camera: true
 */

const CARD_VERSION = "0.3.0";

const TEXT = {
  de: {
    name: "Garten Pool",
    description: "Pool mit Wasserwerten, Pumpe, Rückspülen und Energie.",
    entity: "Pool (Wasserqualität-Sensor)",
    show_camera: "Kamerabild anzeigen",
    missing: "Pool-Sensor nicht gefunden",
    pump: "Pumpe",
    on: "an",
    off: "aus",
    quality: { ok: "Wasser OK", check: "Prüfen", critical: "Kritisch" },
    params: { ph: "pH", orp: "Redox", chlorine: "Chlor", salt: "Salz" },
    water: "Wasserwerte",
    stale: "Letzte Messung ist älter als 12 Stunden",
    measured: "Gemessen",
    pump_backwash: "Pumpe & Filter",
    runtime: "Laufzeit heute",
    backwash: "Seit Rückspülen",
    backwash_due: "Rückspülen fällig",
    backwash_btn: "Rückgespült",
    backwash_confirm: "Filter wurde rückgespült? Der Zähler wird zurückgesetzt.",
    days: "Tage",
    never: "noch nie erfasst",
    energy: "Energie",
    energy_today: "Heute",
    solar_share: "Solar",
    cost_today: "Kosten heute",
    savings_year: "Ersparnis Jahr",
  },
  en: {
    name: "Garten pool",
    description: "Pool with water values, pump, backwash and energy.",
    entity: "Pool (water quality sensor)",
    show_camera: "Show camera image",
    missing: "Pool sensor not found",
    pump: "Pump",
    on: "on",
    off: "off",
    quality: { ok: "Water OK", check: "Check", critical: "Critical" },
    params: { ph: "pH", orp: "Redox", chlorine: "Chlorine", salt: "Salt" },
    water: "Water values",
    stale: "Last measurement is older than 12 hours",
    measured: "Measured",
    pump_backwash: "Pump & filter",
    runtime: "Runtime today",
    backwash: "Since backwash",
    backwash_due: "Backwash due",
    backwash_btn: "Backwashed",
    backwash_confirm: "Filter backwashed? The counter will be reset.",
    days: "days",
    never: "never recorded",
    energy: "Energy",
    energy_today: "Today",
    solar_share: "Solar",
    cost_today: "Cost today",
    savings_year: "Savings this year",
  },
};

const UNITS = { ph: "", orp: "mV", chlorine: "mg/l", salt: "g/l" };
const DIGITS = { ph: 1, orp: 0, chlorine: 2, salt: 1 };

const ICONS = {
  pump: "M19,14.5C19,14.5 21,16.67 21,18A2,2 0 0,1 19,20A2,2 0 0,1 17,18C17,16.67 19,14.5 19,14.5M5,18V9A2,2 0 0,1 3,7A2,2 0 0,1 5,5V4A2,2 0 0,1 7,2H9A2,2 0 0,1 11,4V5H19A2,2 0 0,1 21,7V9L21,11A1,1 0 0,1 22,12A1,1 0 0,1 21,13H17A1,1 0 0,1 16,12A1,1 0 0,1 17,11V9H11V18H12A2,2 0 0,1 14,20V22H2V20A2,2 0 0,1 4,18H5Z",
  clock: "M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22A10,10 0 0,1 2,12A10,10 0 0,1 12,2M12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20A8,8 0 0,0 20,12A8,8 0 0,0 12,4M11,7H13V12L16.5,14.1L15.7,15.4L11,12.6V7Z",
  power: "M11,15H6L13,1V9H18L11,23V15Z",
  water: "M12,20A6,6 0 0,1 6,14C6,10 12,3.25 12,3.25C12,3.25 18,10 18,14A6,6 0 0,1 12,20Z",
  info: "M13,9H11V7H13M13,17H11V11H13M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2Z",
  alert: "M13,14H11V10H13M13,18H11V16H13M1,21H23L12,2L1,21Z",
  filter: "M14,12V19.88C14.04,20.18 13.94,20.5 13.71,20.71C13.32,21.1 12.69,21.1 12.3,20.71L10.29,18.7C10.06,18.47 9.96,18.16 10,17.87V12H9.97L4.21,4.62C3.87,4.19 3.95,3.56 4.38,3.22C4.57,3.08 4.78,3 5,3H19C19.22,3 19.43,3.08 19.62,3.22C20.05,3.56 20.13,4.19 19.79,4.62L14.03,12H14Z",
  solar: "M4,2H20A2,2 0 0,1 22,4V14A2,2 0 0,1 20,16H15V20H18V22H13V16H11V22H6V20H9V16H4A2,2 0 0,1 2,14V4A2,2 0 0,1 4,2M4,4V8H11V4H4M4,14H11V10H4V14M20,14V10H13V14H20M20,4H13V8H20V4Z",
  thermometer: "M15 13V5A3 3 0 0 0 9 5V13A5 5 0 1 0 15 13M12 4A1 1 0 0 1 13 5V8H11V5A1 1 0 0 1 12 4Z",
};

const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );

const icon = (name, size = 18) =>
  `<svg class="icon" viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true"><path d="${ICONS[name]}"/></svg>`;

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

class GartenPoolCard extends HTMLElement {
  static getConfigForm() {
    return {
      schema: [
        {
          name: "entity",
          required: true,
          selector: { entity: { filter: { integration: "garten", domain: "sensor" } } },
        },
        { name: "show_camera", selector: { boolean: {} } },
      ],
      computeLabel: (schema) => {
        const lang = (document.querySelector("home-assistant")?.hass?.language || "en").slice(0, 2);
        return (TEXT[lang] || TEXT.en)[schema.name];
      },
    };
  }

  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find(
      (id) => id.startsWith("sensor.") && hass.states[id].attributes.card_entities
    );
    return { entity: entity || "", show_camera: true };
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("entity is required");
    }
    this._config = { show_camera: true, ...config };
    this._signature = undefined;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    }
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const signature = this._computeSignature();
    if (signature !== this._signature) {
      this._signature = signature;
      this._render();
    }
  }

  getCardSize() {
    return this._config?.show_camera ? 8 : 6;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  // ------------------------------------------------------------------ data

  get _t() {
    const lang = (this._hass?.language || "en").slice(0, 2);
    return TEXT[lang] || TEXT.en;
  }

  get _locale() {
    return this._hass?.locale?.language || this._hass?.language || "en";
  }

  _state(entityId) {
    return entityId ? this._hass.states[entityId] : undefined;
  }

  _num(entityId) {
    const value = parseFloat(this._state(entityId)?.state);
    return Number.isFinite(value) ? value : null;
  }

  _fmt(value, digits = 1) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "–";
    return Number(value).toLocaleString(this._locale, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  }

  _computeSignature() {
    const quality = this._state(this._config?.entity);
    if (!quality) return "missing";
    const attrs = quality.attributes;
    const ids = [
      this._config.entity,
      ...Object.values(attrs.card_entities || {}),
      ...Object.values(attrs.card_sources || {}),
    ];
    return ids
      .map((id) => {
        const s = this._hass.states[id];
        return s ? `${s.state}|${s.last_updated}|${s.attributes.entity_picture || ""}` : "";
      })
      .join(";");
  }

  // ---------------------------------------------------------------- render

  _render() {
    if (!this.shadowRoot || !this._hass || !this._config) return;
    const t = this._t;
    const quality = this._state(this._config.entity);
    if (!quality) {
      this.shadowRoot.innerHTML = `${STYLE}<ha-card><div class="missing">${icon("alert")} ${esc(
        t.missing
      )}: ${esc(this._config.entity)}</div></ha-card>`;
      return;
    }
    const attrs = quality.attributes;
    const ents = attrs.card_entities || {};
    const src = attrs.card_sources || {};
    this.shadowRoot.innerHTML = `${STYLE}<ha-card>
      ${this._renderHero(quality, ents, src)}
      ${this._renderWater(attrs, ents)}
      ${this._renderPump(ents)}
      ${this._renderEnergy(ents)}
    </ha-card>`;
  }

  _renderHero(quality, ents, src) {
    const t = this._t;
    const name = quality.attributes.pool_name || "Pool";
    const temp = this._num(src.temperature_entity);
    const pump = this._state(src.pump_entity);
    const pumpOn = pump?.state === "on";
    const power = this._num(src.power_entity);
    const camera = this._config.show_camera ? this._state(src.camera_entity) : undefined;
    const picture = camera?.attributes?.entity_picture;
    const level = quality.state;
    const badge = t.quality[level]
      ? `<span class="badge q-${esc(level)}" data-more="${esc(this._config.entity)}">${icon(
          "water",
          14
        )}${esc(t.quality[level])}</span>`
      : "";
    const pumpLabel = `${t.pump} ${pumpOn ? t.on : t.off}${
      pumpOn && power !== null ? ` · ${this._fmt(power, 0)} W` : ""
    }`;
    return `<div class="hero ${picture ? "with-image" : ""}" ${
      picture ? `style="background-image:url(${esc(JSON.stringify(picture))})"` : ""
    }>
      <div class="hero-shade"></div>
      <div class="hero-top">
        <div class="title">${esc(name)}</div>
        ${badge}
      </div>
      <div class="hero-bottom">
        <div class="temp" data-more="${esc(src.temperature_entity || "")}">
          ${temp !== null ? `${this._fmt(temp, 1)}<span class="unit">°C</span>` : ""}
        </div>
        ${
          pump
            ? `<button class="pump ${pumpOn ? "on" : ""}" data-toggle="${esc(
                src.pump_entity
              )}" title="${esc(pumpLabel)}">${icon("pump", 18)}<span>${esc(pumpLabel)}</span></button>`
            : ""
        }
      </div>
    </div>`;
  }

  _renderWater(attrs, ents) {
    const t = this._t;
    const values = attrs.values || {};
    const ranges = attrs.ranges || {};
    const params = Object.keys(values);
    if (!params.length && !attrs.guidance) return "";
    const tiles = params
      .map((param) => {
        const value = values[param];
        const status = this._state(ents[`${param}_status`])?.state;
        const range = ranges[param];
        return `<div class="tile" data-more="${esc(ents[`${param}_status`] || "")}">
          <div class="tile-head"><span class="dot q-${esc(status || "none")}"></span>${esc(
            t.params[param] || param
          )}</div>
          <div class="tile-value">${this._fmt(value, DIGITS[param] ?? 1)}<span class="unit">${esc(
            UNITS[param] || ""
          )}</span></div>
          ${range ? this._rangeBar(value, range) : ""}
        </div>`;
      })
      .join("");
    const stale = this._state(ents.measurement_stale)?.state === "on";
    const measured = attrs.last_measurement
      ? new Date(attrs.last_measurement).toLocaleString(this._locale, {
          day: "2-digit",
          month: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        })
      : null;
    return `<div class="section">
      <div class="section-head"><span>${esc(t.water)}</span>${
        measured ? `<span class="muted">${esc(t.measured)} ${esc(measured)}</span>` : ""
      }</div>
      ${tiles ? `<div class="tiles">${tiles}</div>` : ""}
      ${
        stale
          ? `<div class="note warn">${icon("alert", 16)}<span>${esc(t.stale)}</span></div>`
          : ""
      }
      ${
        attrs.guidance
          ? `<div class="note">${icon("info", 16)}<span>${esc(attrs.guidance)}</span></div>`
          : ""
      }
    </div>`;
  }

  _rangeBar(value, [checkMin, okMin, okMax, checkMax]) {
    const pad = (checkMax - checkMin) * 0.15;
    const lo = checkMin - pad;
    const hi = checkMax + pad;
    const pos = (v) => ((clamp(v, lo, hi) - lo) / (hi - lo)) * 100;
    const marker =
      value === null || value === undefined
        ? ""
        : `<span class="marker" style="left:${pos(value).toFixed(1)}%"></span>`;
    return `<div class="range" aria-hidden="true">
      <span class="seg q-critical" style="left:0;width:${pos(checkMin)}%"></span>
      <span class="seg q-check" style="left:${pos(checkMin)}%;width:${pos(okMin) - pos(checkMin)}%"></span>
      <span class="seg q-ok" style="left:${pos(okMin)}%;width:${pos(okMax) - pos(okMin)}%"></span>
      <span class="seg q-check" style="left:${pos(okMax)}%;width:${pos(checkMax) - pos(okMax)}%"></span>
      <span class="seg q-critical" style="left:${pos(checkMax)}%;width:${100 - pos(checkMax)}%"></span>
      ${marker}
    </div>`;
  }

  _renderPump(ents) {
    const t = this._t;
    const runtimeState = this._state(ents.runtime_today);
    const backwashState = this._state(ents.backwash_hours);
    if (!runtimeState && !backwashState) return "";
    const runtime = this._num(ents.runtime_today);
    const recommended = parseFloat(runtimeState?.attributes?.recommended_runtime);
    const hours = this._num(ents.backwash_hours);
    const interval = parseFloat(backwashState?.attributes?.interval_hours);
    const days = backwashState?.attributes?.days_since_backwash;
    const due = this._state(ents.backwash_due)?.state === "on";
    const runtimeBar = this._progress(
      runtime,
      Number.isFinite(recommended) ? recommended : null,
      `${this._fmt(runtime, 1)}${Number.isFinite(recommended) ? ` / ${this._fmt(recommended, 1)}` : ""} h`,
      "var(--garten-water)"
    );
    const backwashText = `${this._fmt(hours, 0)} / ${this._fmt(interval, 0)} h · ${
      days === null || days === undefined ? t.never : `${this._fmt(days, 0)} ${t.days}`
    }`;
    const backwashBar = this._progress(
      hours,
      Number.isFinite(interval) ? interval : null,
      backwashText,
      due ? "var(--garten-critical)" : "var(--garten-ok)"
    );
    return `<div class="section">
      <div class="section-head"><span>${esc(t.pump_backwash)}</span>${
        due ? `<span class="pill q-critical">${icon("alert", 14)}${esc(t.backwash_due)}</span>` : ""
      }</div>
      <div class="row" data-more="${esc(ents.runtime_today || "")}">
        <div class="row-label">${icon("clock", 16)}${esc(t.runtime)}</div>${runtimeBar}
      </div>
      <div class="row" data-more="${esc(ents.backwash_hours || "")}">
        <div class="row-label">${icon("filter", 16)}${esc(t.backwash)}</div>${backwashBar}
      </div>
      ${
        ents.backwash_done
          ? `<div class="actions"><button class="action ${due ? "primary" : ""}" data-backwash="${esc(
              ents.backwash_done
            )}">${icon("filter", 16)}${esc(t.backwash_btn)}</button></div>`
          : ""
      }
    </div>`;
  }

  _progress(value, max, label, color) {
    const pct = value !== null && max ? clamp((value / max) * 100, 0, 100) : 0;
    return `<div class="progress">
      <div class="bar"><span style="width:${pct.toFixed(1)}%;background:${color}"></span></div>
      <div class="progress-label">${esc(label)}</div>
    </div>`;
  }

  _renderEnergy(ents) {
    const t = this._t;
    if (!ents.energy_today) return "";
    const kwh = this._num(ents.energy_today);
    const share = this._num(ents.solar_share_today);
    const cost = this._num(ents.cost_today);
    const savings = this._num(ents.solar_savings_year);
    const stat = (entity, iconName, value, label, extra = "") => `
      <div class="stat" data-more="${esc(entity || "")}">
        <div class="stat-value">${icon(iconName, 16)}${value}</div>
        <div class="stat-label">${esc(label)}</div>${extra}
      </div>`;
    const shareBar =
      share !== null
        ? `<div class="bar thin"><span style="width:${clamp(share, 0, 100).toFixed(
            0
          )}%;background:var(--garten-solar)"></span></div>`
        : "";
    const euro = (v) => (v === null ? "–" : `${this._fmt(v, 2)} €`);
    return `<div class="section">
      <div class="section-head"><span>${esc(t.energy)}</span></div>
      <div class="stats">
        ${stat(ents.energy_today, "power", `${this._fmt(kwh, 2)} kWh`, t.energy_today)}
        ${
          ents.solar_share_today
            ? stat(
                ents.solar_share_today,
                "solar",
                share === null ? "–" : `${this._fmt(share, 0)} %`,
                t.solar_share,
                shareBar
              )
            : ""
        }
        ${stat(ents.cost_today, "power", euro(cost), t.cost_today)}
        ${
          ents.solar_savings_year
            ? stat(ents.solar_savings_year, "solar", euro(savings), t.savings_year)
            : ""
        }
      </div>
    </div>`;
  }

  // --------------------------------------------------------------- actions

  _onClick(ev) {
    const path = ev.composedPath();
    const target = path.find((el) => el instanceof HTMLElement && el.dataset && Object.keys(el.dataset).length);
    if (!target || !this._hass) return;
    const { toggle, backwash, more } = target.dataset;
    if (toggle) {
      this._hass.callService("homeassistant", "toggle", { entity_id: toggle });
    } else if (backwash) {
      if (window.confirm(this._t.backwash_confirm)) {
        this._hass.callService("button", "press", { entity_id: backwash });
      }
    } else if (more) {
      this.dispatchEvent(
        new CustomEvent("hass-more-info", { detail: { entityId: more }, bubbles: true, composed: true })
      );
    }
  }
}

const STYLE = `<style>
  :host {
    --garten-ok: var(--success-color, #43a047);
    --garten-check: var(--warning-color, #ffa000);
    --garten-critical: var(--error-color, #db4437);
    --garten-water: #0288d1;
    --garten-solar: #f9a825;
    --garten-track: rgba(127, 127, 127, 0.2);
  }
  ha-card { overflow: hidden; }
  .icon { fill: currentColor; flex: none; }
  .missing { padding: 16px; display: flex; gap: 8px; align-items: center; color: var(--garten-critical); }
  .hero {
    position: relative; min-height: 92px; padding: 16px; color: #fff;
    display: flex; flex-direction: column; justify-content: space-between; gap: 12px;
    background: linear-gradient(135deg, #0277bd 0%, #26c6da 100%);
    background-size: cover; background-position: center;
  }
  .hero.with-image { min-height: 180px; }
  .hero-shade {
    position: absolute; inset: 0; pointer-events: none;
    background: linear-gradient(180deg, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0) 45%, rgba(0,0,0,0.55) 100%);
  }
  .hero > :not(.hero-shade) { position: relative; }
  .hero-top, .hero-bottom { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
  .hero-bottom { align-items: flex-end; }
  .title { font-size: 1.25rem; font-weight: 600; text-shadow: 0 1px 3px rgba(0,0,0,0.4); }
  .temp { font-size: 2.4rem; font-weight: 300; line-height: 1; cursor: pointer; text-shadow: 0 1px 4px rgba(0,0,0,0.4); }
  .temp .unit { font-size: 1.1rem; margin-left: 2px; opacity: 0.9; }
  .badge, .pill {
    display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border-radius: 999px;
    font-size: 0.8rem; font-weight: 600; color: #fff; cursor: pointer; white-space: nowrap;
  }
  .badge.q-ok, .pill.q-ok { background: var(--garten-ok); }
  .badge.q-check, .pill.q-check { background: var(--garten-check); }
  .badge.q-critical, .pill.q-critical { background: var(--garten-critical); }
  .pump {
    display: inline-flex; align-items: center; gap: 6px; border: 1px solid rgba(255,255,255,0.6);
    background: rgba(0,0,0,0.25); color: #fff; border-radius: 999px; padding: 6px 12px;
    font: inherit; font-size: 0.9rem; cursor: pointer; backdrop-filter: blur(4px);
  }
  .pump.on { background: rgba(255,255,255,0.95); color: var(--garten-water); border-color: transparent; }
  .section { padding: 12px 16px; border-top: 1px solid var(--divider-color, rgba(127,127,127,0.2)); }
  .section-head {
    display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 10px;
    font-weight: 600; color: var(--primary-text-color);
  }
  .muted { font-weight: 400; font-size: 0.8rem; color: var(--secondary-text-color); }
  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 8px; }
  .tile {
    padding: 10px 12px; border-radius: 12px; cursor: pointer;
    background: var(--secondary-background-color, rgba(127,127,127,0.08));
  }
  .tile-head { display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: var(--secondary-text-color); }
  .tile-value { font-size: 1.5rem; font-weight: 500; margin: 4px 0 8px; color: var(--primary-text-color); }
  .tile-value .unit, .stat-value .unit { font-size: 0.8rem; margin-left: 3px; color: var(--secondary-text-color); }
  .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--garten-track); }
  .dot.q-ok { background: var(--garten-ok); }
  .dot.q-check { background: var(--garten-check); }
  .dot.q-critical { background: var(--garten-critical); }
  .range { position: relative; height: 6px; border-radius: 3px; overflow: visible; background: var(--garten-track); }
  .seg { position: absolute; top: 0; bottom: 0; opacity: 0.55; }
  .seg:first-child { border-radius: 3px 0 0 3px; }
  .seg:nth-last-child(2) { border-radius: 0 3px 3px 0; }
  .seg.q-ok { background: var(--garten-ok); opacity: 0.8; }
  .seg.q-check { background: var(--garten-check); }
  .seg.q-critical { background: var(--garten-critical); }
  .marker {
    position: absolute; top: -4px; width: 4px; height: 14px; margin-left: -2px; border-radius: 2px;
    background: var(--primary-text-color); box-shadow: 0 0 0 2px var(--card-background-color, #fff);
  }
  .note {
    display: flex; gap: 8px; align-items: flex-start; margin-top: 10px; padding: 8px 10px; border-radius: 10px;
    font-size: 0.9rem; color: var(--primary-text-color);
    background: color-mix(in srgb, var(--garten-water) 12%, transparent);
  }
  .note .icon { color: var(--garten-water); margin-top: 1px; }
  .note.warn { background: color-mix(in srgb, var(--garten-check) 16%, transparent); }
  .note.warn .icon { color: var(--garten-check); }
  .row { display: grid; grid-template-columns: minmax(120px, 38%) 1fr; gap: 12px; align-items: center; margin: 8px 0; cursor: pointer; }
  .row-label { display: flex; align-items: center; gap: 6px; font-size: 0.9rem; color: var(--secondary-text-color); }
  .progress { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
  .progress-label { font-size: 0.8rem; color: var(--primary-text-color); text-align: right; }
  .bar { height: 8px; border-radius: 4px; background: var(--garten-track); overflow: hidden; }
  .bar.thin { height: 4px; margin-top: 6px; }
  .bar > span { display: block; height: 100%; border-radius: inherit; transition: width 0.4s ease; }
  .actions { display: flex; justify-content: flex-end; margin-top: 6px; }
  .action {
    display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: 999px;
    border: 1px solid var(--divider-color, rgba(127,127,127,0.3)); background: transparent;
    color: var(--primary-text-color); font: inherit; font-size: 0.9rem; cursor: pointer;
  }
  .action.primary { background: var(--garten-critical); border-color: transparent; color: #fff; }
  .stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .stat-value { white-space: nowrap; }
  .stat { padding: 8px 10px; border-radius: 12px; cursor: pointer; background: var(--secondary-background-color, rgba(127,127,127,0.08)); }
  .stat-value { display: flex; align-items: center; gap: 6px; font-size: 1.05rem; font-weight: 500; color: var(--primary-text-color); }
  .stat-value .icon { color: var(--secondary-text-color); }
  .stat-label { font-size: 0.8rem; color: var(--secondary-text-color); margin-top: 2px; }
  button:focus-visible, .tile:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
  @media (max-width: 420px) {
    .row { grid-template-columns: 1fr; gap: 4px; }
    .progress-label { text-align: left; }
    .temp { font-size: 2rem; }
  }
</style>`;

if (!customElements.get("garten-pool-card")) {
  customElements.define("garten-pool-card", GartenPoolCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "garten-pool-card",
    name: TEXT.de.name,
    description: TEXT.de.description,
    preview: true,
    documentationURL: "https://github.com/passi277/HACS-Garten",
  });
  console.info(`%c GARTEN-POOL-CARD %c ${CARD_VERSION} `, "color:#fff;background:#0288d1", "color:#0288d1");
}
