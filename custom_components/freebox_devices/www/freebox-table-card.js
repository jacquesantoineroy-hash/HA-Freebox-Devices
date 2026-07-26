/**
 * freebox-table-card
 *
 * Carte Lovelace custom : vrai tableau HTML (thead/tbody, lignes alignées,
 * en-tête collant) listant les appareils connectés vus par l'intégration
 * Freebox Devices, avec débit, accès web et blacklist Wifi. Remplace
 * l'ancienne mise en page en tuiles (auto-entities + grid) qui ne
 * s'alignait pas proprement en lignes et affichait un badge "maison" en
 * exposant sur chaque icône (artefact de hui-tile-card).
 *
 * Pas de build, pas de dépendance externe : simple élément custom vanilla
 * JS, servi statiquement par l'intégration et auto-chargé (voir
 * __init__.py::_async_register_frontend_card).
 *
 * Interactions :
 *  - clic sur le nom de l'appareil / le débit / l'accès web -> more-info
 *  - clic sur l'icône Blacklist -> bascule directe (verrouille/déverrouille
 *    le Wifi de l'appareil), pas de confirmation (même comportement que
 *    l'ancienne tuile avec icon_tap_action: toggle)
 */

class FreeboxTableCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};

    if (this.shadowRoot) return;

    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 0; overflow: hidden; }
        .header {
          padding: 16px 16px 0 16px;
          font-size: 1.2em;
          font-weight: 400;
          color: var(--ha-card-header-color, --primary-text-color);
        }
        .wrap { overflow-x: auto; }
        table {
          width: 100%;
          border-collapse: collapse;
          font-size: 14px;
        }
        thead th {
          position: sticky;
          top: 0;
          background: var(--card-background-color, #1c1c1c);
          text-align: left;
          padding: 10px 12px;
          font-weight: 600;
          color: var(--secondary-text-color);
          border-bottom: 2px solid var(--divider-color, #333);
          white-space: nowrap;
        }
        tbody tr {
          border-bottom: 1px solid var(--divider-color, #2a2a2a);
        }
        tbody tr:nth-child(even) {
          background: var(--secondary-background-color, rgba(255, 255, 255, 0.025));
        }
        tbody tr:hover {
          background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.08);
        }
        tbody td {
          padding: 8px 12px;
          vertical-align: middle;
        }
        .name-cell {
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 10px;
          max-width: 260px;
        }
        .name-cell ha-icon {
          color: var(--state-icon-color, #44739e);
          flex-shrink: 0;
        }
        .name-text {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .clickable { cursor: pointer; }
        .cell-icon { display: flex; align-items: center; gap: 6px; white-space: nowrap; }
        .cell-icon ha-icon { flex-shrink: 0; --mdc-icon-size: 20px; }
        .muted { color: var(--secondary-text-color); }
        .empty { padding: 24px; text-align: center; color: var(--secondary-text-color); }
      </style>
      <ha-card>
        <div class="header"></div>
        <div class="wrap">
          <table>
            <thead>
              <tr>
                <th>Appareil</th>
                <th>Débit</th>
                <th>Accès web</th>
                <th>Blacklist</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </ha-card>
    `;

    this._header = this.shadowRoot.querySelector(".header");
    this._tbody = this.shadowRoot.querySelector("tbody");
    this._tbody.addEventListener("click", (ev) => this._onClick(ev));

    if (this._config.title) {
      this._header.textContent = this._config.title;
      this._header.style.display = "block";
    } else {
      this._header.style.display = "none";
    }
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  _esc(value) {
    return String(value).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  _onClick(ev) {
    const td = ev.target.closest("td[data-entity]");
    if (!td || !this._hass) return;
    const entityId = td.dataset.entity;

    if (td.dataset.action === "toggle-lock") {
      const state = this._hass.states[entityId];
      const service = state && state.state === "locked" ? "unlock" : "lock";
      this._hass.callService("lock", service, { entity_id: entityId });
      return;
    }

    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        bubbles: true,
        composed: true,
        detail: { entityId },
      })
    );
  }

  _render() {
    if (!this._tbody || !this._hass) return;
    const hass = this._hass;
    const entities = hass.entities || {};
    const states = hass.states;

    const trackers = Object.values(entities).filter(
      (e) => e.platform === "freebox_devices" && e.entity_id.startsWith("device_tracker.")
    );

    const rows = [];
    for (const tracker of trackers) {
      const trackerState = states[tracker.entity_id];
      if (!trackerState || trackerState.state !== "home") continue;

      const deviceId = tracker.device_id;
      const siblings = deviceId
        ? Object.values(entities).filter((e) => e.device_id === deviceId)
        : [];

      const hideEnt = siblings.find((e) => e.entity_id.includes("_masque_du_dashboard"));
      if (hideEnt && states[hideEnt.entity_id] && states[hideEnt.entity_id].state === "on") {
        continue;
      }

      const lockEnt = siblings.find((e) => e.entity_id.startsWith("lock."));
      const webEnt = siblings.find((e) => e.entity_id.includes("_acces_web"));
      const rxEnt = siblings.find((e) => e.entity_id.includes("_debit_descendant"));

      rows.push({
        name: trackerState.attributes.friendly_name || tracker.entity_id,
        trackerId: tracker.entity_id,
        icon: trackerState.attributes.icon || "mdi:devices",
        connType: trackerState.attributes.connectivity_type,
        lockEnt,
        webEnt,
        rxEnt,
      });
    }

    rows.sort((a, b) => a.name.localeCompare(b.name, "fr"));

    if (!rows.length) {
      this._tbody.innerHTML = `<tr><td colspan="4" class="empty">Aucun appareil connecté</td></tr>`;
      return;
    }

    this._tbody.innerHTML = rows.map((r) => this._rowHtml(r)).join("");
  }

  _rowHtml(r) {
    const hass = this._hass;

    let rxCell;
    if (r.rxEnt) {
      const st = hass.states[r.rxEnt.entity_id];
      const val = st ? `${this._esc(st.state)} ${this._esc(st.attributes.unit_of_measurement || "")}` : "–";
      rxCell = `<td class="clickable" data-entity="${r.rxEnt.entity_id}">
        <span class="cell-icon"><ha-icon icon="mdi:speedometer"></ha-icon>${val}</span>
      </td>`;
    } else {
      rxCell = `<td class="muted">–</td>`;
    }

    let webCell;
    if (r.webEnt) {
      const st = hass.states[r.webEnt.entity_id];
      const state = st ? st.state : "allowed";
      const map = {
        allowed: ["mdi:lock-open-variant", "#43a047"],
        denied: ["mdi:lock", "#e53935"],
        webonly: ["mdi:lock-alert", "#fb8c00"],
      };
      const [icon, color] = map[state] || map.allowed;
      webCell = `<td class="clickable" data-entity="${r.webEnt.entity_id}">
        <span class="cell-icon"><ha-icon icon="${icon}" style="color:${color}"></ha-icon></span>
      </td>`;
    } else {
      webCell = `<td><span class="cell-icon"><ha-icon icon="mdi:lock-open-variant" style="color:#43a047"></ha-icon></span></td>`;
    }

    let blacklistCell;
    if (r.lockEnt && r.connType === "wifi") {
      const st = hass.states[r.lockEnt.entity_id];
      const locked = st && st.state === "locked";
      const icon = locked ? "mdi:close-circle" : "mdi:check-circle";
      const color = locked ? "#9e9e9e" : "#43a047";
      blacklistCell = `<td class="clickable" data-entity="${r.lockEnt.entity_id}" data-action="toggle-lock">
        <span class="cell-icon"><ha-icon icon="${icon}" style="color:${color}"></ha-icon></span>
      </td>`;
    } else {
      blacklistCell = `<td class="muted"><ha-icon icon="mdi:minus"></ha-icon></td>`;
    }

    return `<tr>
      <td class="name-cell" data-entity="${r.trackerId}">
        <ha-icon icon="${this._esc(r.icon)}"></ha-icon>
        <span class="name-text">${this._esc(r.name)}</span>
      </td>
      ${rxCell}
      ${webCell}
      ${blacklistCell}
    </tr>`;
  }
}

customElements.define("freebox-table-card", FreeboxTableCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "freebox-table-card",
  name: "Freebox — Tableau appareils",
  description: "Tableau des appareils connectés (débit, accès web, blacklist), inclus avec l'intégration Freebox Devices.",
});
