/**
 * freebox-table-card
 *
 * Carte Lovelace custom : liste d'appareils connectés vus par l'intégration
 * Freebox Devices, en pilules arrondies façon carte "tuile" HA (cf. le
 * style déjà utilisé sur la vue Statistiques : icône à gauche, libellé,
 * valeur). Une pilule par appareil : icône de connexion (Wifi/Ethernet),
 * nom, débit descendant/montant (simples flèches ↓/↑), puis 2 icônes
 * d'action à droite (accès web, blacklist).
 *
 * Cliquer sur une pilule ouvre un écran de détail unique (dialog natif
 * <dialog>) regroupant : état/débit/signal, historique de connexion
 * (dernières transitions connecté/déconnecté), renommage de l'appareil
 * (device registry), et les boutons d'action (couper/rétablir l'accès web
 * via le profil de contrôle parental qui couvre l'appareil, bloquer/
 * débloquer le Wifi = blacklist complète). Remplace le comportement
 * précédent qui dispersait ces informations sur 3 clics différents
 * (more-info du tracker / du sensor accès web / toggle direct du lock) —
 * demande explicite de l'utilisateur ("un écran" unique avec stats +
 * historique + boutons, puis "je dois pouvoir couper l'accès web" et
 * "renommer les appareils").
 *
 * Pas de build, pas de dépendance externe : simple élément custom vanilla
 * JS, servi statiquement par l'intégration et auto-chargé (voir
 * __init__.py::_async_register_frontend_card).
 */

class FreeboxTableCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};

    if (this.shadowRoot) return;

    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 0; }
        .header {
          padding: 16px 16px 0 16px;
          font-size: 1.2em;
          font-weight: 400;
          color: var(--ha-card-header-color, var(--primary-text-color));
        }
        .list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          padding: 16px;
        }
        .row {
          display: flex;
          align-items: center;
          gap: 12px;
          background: var(--ha-card-background, var(--card-background-color, #1c1c1c));
          border-radius: 18px;
          padding: 10px 16px;
          cursor: pointer;
          box-shadow: var(--ha-card-box-shadow, none);
          border: 1px solid var(--divider-color, rgba(255, 255, 255, 0.06));
        }
        .row:hover { filter: brightness(1.1); }
        .device-icon {
          color: var(--state-icon-color, #44739e);
          flex-shrink: 0;
          --mdc-icon-size: 22px;
        }
        .name {
          flex: 1 1 auto;
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-weight: 500;
        }
        .rate {
          display: flex;
          align-items: center;
          gap: 2px;
          font-size: 0.82em;
          color: var(--secondary-text-color);
          white-space: nowrap;
          flex-shrink: 0;
          min-width: 62px;
        }
        .rate ha-icon { --mdc-icon-size: 16px; flex-shrink: 0; }
        .rate.down ha-icon { color: #42a5f5; }
        .rate.up ha-icon { color: #ab47bc; }
        .action {
          flex-shrink: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          --mdc-icon-size: 22px;
        }
        .empty { padding: 24px; text-align: center; color: var(--secondary-text-color); }

        /* Écran de détail (dialog native, top-layer même depuis le shadow DOM).
           Centrage explicite en position fixed : le centrage UA natif
           (margin: auto sur position: absolute) n'est pas fiable pour un
           <dialog> hébergé dans un shadow DOM sur tous les moteurs. */
        dialog.device-dialog {
          border: none;
          padding: 0;
          background: transparent;
          width: auto;
          max-width: none;
          max-height: none;
          color: var(--primary-text-color);
          position: fixed;
          top: 50%;
          left: 50%;
          margin: 0;
          transform: translate(-50%, -50%);
        }
        dialog.device-dialog::backdrop { background: rgba(0, 0, 0, 0.55); }
        .dialog-inner {
          background: var(--card-background-color, #1c1c1c);
          border-radius: 20px;
          width: min(420px, 92vw);
          max-height: 85vh;
          display: flex;
          flex-direction: column;
        }
        .dialog-head {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 16px 12px 8px 16px;
          flex-shrink: 0;
        }
        .dialog-icon { --mdc-icon-size: 26px; color: var(--state-icon-color, #44739e); flex-shrink: 0; }
        .dialog-title {
          flex: 1 1 auto;
          font-size: 1.1em;
          font-weight: 600;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .dialog-close {
          background: none;
          border: none;
          color: var(--secondary-text-color);
          font-size: 1.3em;
          line-height: 1;
          cursor: pointer;
          padding: 6px 10px;
          border-radius: 50%;
        }
        .dialog-close:hover { background: var(--secondary-background-color, rgba(255,255,255,0.08)); }
        .dialog-rename {
          background: none;
          border: none;
          color: var(--secondary-text-color);
          font-size: 1em;
          cursor: pointer;
          padding: 6px 8px;
          border-radius: 50%;
          flex-shrink: 0;
        }
        .dialog-rename:hover { background: var(--secondary-background-color, rgba(255,255,255,0.08)); }
        .dialog-warning {
          font-size: 0.76em;
          color: #fb8c00;
          margin-top: 6px;
        }
        .dialog-body { padding: 0 16px 16px 16px; overflow-y: auto; }
        .dialog-section { margin-top: 14px; }
        .dialog-section h4 {
          margin: 0 0 6px 0;
          font-size: 0.78em;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          color: var(--secondary-text-color);
          font-weight: 600;
        }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .stat-item {
          background: var(--secondary-background-color, rgba(255, 255, 255, 0.04));
          border-radius: 12px;
          padding: 8px 10px;
        }
        .stat-item .label { font-size: 0.72em; color: var(--secondary-text-color); }
        .stat-item .value { font-size: 0.92em; font-weight: 500; margin-top: 2px; }
        .history-list {
          display: flex;
          flex-direction: column;
          gap: 4px;
          font-size: 0.83em;
          max-height: 160px;
          overflow-y: auto;
        }
        .history-item {
          display: flex;
          justify-content: space-between;
          gap: 8px;
          padding: 5px 10px;
          border-radius: 8px;
          background: var(--secondary-background-color, rgba(255, 255, 255, 0.03));
        }
        .history-item .state.home { color: #43a047; }
        .history-item .state.not_home { color: var(--secondary-text-color); }
        .dialog-btn {
          width: 100%;
          padding: 11px;
          border-radius: 12px;
          border: none;
          font-weight: 600;
          font-size: 0.92em;
          cursor: pointer;
          margin-top: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
        }
        .dialog-btn.danger { background: #e53935; color: #fff; }
        .dialog-btn.success { background: #43a047; color: #fff; }
        .dialog-btn.neutral {
          background: var(--secondary-background-color, rgba(255, 255, 255, 0.08));
          color: var(--primary-text-color);
        }
        .dialog-btn[disabled] { opacity: 0.45; cursor: not-allowed; }
        .dialog-hint { font-size: 0.76em; color: var(--secondary-text-color); margin-top: 6px; }
      </style>
      <ha-card>
        <div class="header"></div>
        <div class="list"></div>
      </ha-card>
      <dialog class="device-dialog">
        <div class="dialog-inner">
          <div class="dialog-head">
            <ha-icon class="dialog-icon"></ha-icon>
            <span class="dialog-title"></span>
            <button class="dialog-rename" aria-label="Renommer">✎</button>
            <button class="dialog-close" aria-label="Fermer">✕</button>
          </div>
          <div class="dialog-body"></div>
        </div>
      </dialog>
    `;

    this._header = this.shadowRoot.querySelector(".header");
    this._list = this.shadowRoot.querySelector(".list");
    this._list.addEventListener("click", (ev) => this._onListClick(ev));

    this._dialog = this.shadowRoot.querySelector("dialog.device-dialog");
    this._dialogIcon = this.shadowRoot.querySelector(".dialog-icon");
    this._dialogTitle = this.shadowRoot.querySelector(".dialog-title");
    this._dialogBody = this.shadowRoot.querySelector(".dialog-body");
    this.shadowRoot.querySelector(".dialog-rename").addEventListener("click", () => this._onRenameClick());
    this.shadowRoot.querySelector(".dialog-close").addEventListener("click", () => this._dialog.close());
    this._dialog.addEventListener("click", (ev) => {
      if (ev.target === this._dialog) this._dialog.close();
    });
    this._dialog.addEventListener("close", () => {
      this._activeDialogTrackerId = null;
    });
    this._dialogBody.addEventListener("click", (ev) => this._onDialogClick(ev));

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
    if (this._activeDialogTrackerId && this._rowsById) {
      const row = this._rowsById[this._activeDialogTrackerId];
      if (row) this._renderDialogBody(row);
    }
  }

  getCardSize() {
    return 6;
  }

  _esc(value) {
    return String(value).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  _fireMoreInfo(entityId) {
    if (!entityId) return;
    this.dispatchEvent(
      new CustomEvent("hass-more-info", { bubbles: true, composed: true, detail: { entityId } })
    );
  }

  _navigate(path) {
    this._dialog.close();
    window.history.pushState(null, "", path);
    window.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
  }

  _onListClick(ev) {
    if (!this._hass) return;

    const actionEl = ev.target.closest('[data-role="action"]');
    if (actionEl) {
      const entityId = actionEl.dataset.entity;
      if (!entityId) return;
      if (actionEl.dataset.action === "toggle-lock") {
        const state = this._hass.states[entityId];
        const service = state && state.state === "locked" ? "unlock" : "lock";
        this._hass.callService("lock", service, { entity_id: entityId });
      } else {
        this._fireMoreInfo(entityId);
      }
      return;
    }

    const rowEl = ev.target.closest(".row");
    if (rowEl && rowEl.dataset.entity && this._rowsById) {
      const row = this._rowsById[rowEl.dataset.entity];
      if (row) this._openDialog(row);
    }
  }

  _openDialog(row) {
    this._activeDialogTrackerId = row.trackerId;
    this._dialogIcon.setAttribute("icon", row.icon);
    this._dialogTitle.textContent = row.name;
    this._renderDialogBody(row);
    if (typeof this._dialog.showModal === "function") {
      this._dialog.showModal();
    }
    this._loadHistory(row.trackerId);
  }

  _onDialogClick(ev) {
    const btn = ev.target.closest("button[data-role]");
    if (!btn || !this._hass) return;

    if (btn.dataset.role === "toggle-lock") {
      const entityId = btn.dataset.entity;
      const state = this._hass.states[entityId];
      const service = state && state.state === "locked" ? "unlock" : "lock";
      this._hass.callService("lock", service, { entity_id: entityId });
      return;
    }
    if (btn.dataset.role === "goto-profils") {
      this._navigate(btn.dataset.path || "/dashboard-freebox/profils");
      return;
    }
    if (btn.dataset.role === "select-option") {
      const entityId = btn.dataset.entity;
      const option = btn.dataset.option;
      if (entityId && option) {
        this._hass.callService("select", "select_option", { entity_id: entityId, option });
      }
      return;
    }
    if (btn.dataset.role === "more-info") {
      this._fireMoreInfo(btn.dataset.entity);
    }
  }

  async _onRenameClick() {
    if (!this._activeDialogTrackerId || !this._hass || !this._rowsById) return;
    const row = this._rowsById[this._activeDialogTrackerId];
    if (!row || !row.deviceId) return;

    const next = window.prompt("Renommer l'appareil", row.name);
    if (next === null) return;
    const trimmed = next.trim();
    if (!trimmed || trimmed === row.name) return;

    try {
      await this._hass.connection.sendMessagePromise({
        type: "config/device_registry/update",
        device_id: row.deviceId,
        name_by_user: trimmed,
      });
      this._dialogTitle.textContent = trimmed;
    } catch (err) {
      window.alert("Impossible de renommer l'appareil : " + (err && err.message ? err.message : err));
    }
  }

  _render() {
    if (!this._list || !this._hass) return;
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
      const txEnt = siblings.find((e) => e.entity_id.includes("_debit_montant"));
      const sigEnt = siblings.find((e) => e.entity_id.includes("_signal_wifi"));

      rows.push({
        name: trackerState.attributes.friendly_name || tracker.entity_id,
        trackerId: tracker.entity_id,
        deviceId,
        mac: trackerState.attributes.mac,
        icon: trackerState.attributes.icon || "mdi:devices",
        connType: trackerState.attributes.connectivity_type,
        lockEnt,
        webEnt,
        rxEnt,
        txEnt,
        sigEnt,
      });
    }

    rows.sort((a, b) => a.name.localeCompare(b.name, "fr"));

    this._rowsById = {};
    for (const r of rows) this._rowsById[r.trackerId] = r;

    if (!rows.length) {
      this._list.innerHTML = `<div class="empty">Aucun appareil connecté</div>`;
      return;
    }

    this._list.innerHTML = rows.map((r) => this._rowHtml(r)).join("");
  }

  _rateHtml(ent, direction) {
    const icon = direction === "down" ? "mdi:arrow-down-bold" : "mdi:arrow-up-bold";
    if (!ent) {
      return `<span class="rate ${direction}"><ha-icon icon="${icon}"></ha-icon>–</span>`;
    }
    const st = this._hass.states[ent.entity_id];
    const unknown = !st || ["unknown", "unavailable"].includes(st.state);
    const val = unknown
      ? "–"
      : `${this._esc(st.state)} ${this._esc(st.attributes.unit_of_measurement || "")}`;
    return `<span class="rate ${direction}" data-role="action" data-entity="${ent.entity_id}">
      <ha-icon icon="${icon}"></ha-icon>${val}
    </span>`;
  }

  _rowHtml(r) {
    const hass = this._hass;

    let webAction;
    if (r.webEnt) {
      const st = hass.states[r.webEnt.entity_id];
      const state = st ? st.state : "allowed";
      const map = {
        allowed: ["mdi:lock-open-variant", "#43a047"],
        denied: ["mdi:lock", "#e53935"],
        webonly: ["mdi:lock-alert", "#fb8c00"],
      };
      const [icon, color] = map[state] || map.allowed;
      webAction = `<span class="action" data-role="action" data-entity="${r.webEnt.entity_id}">
        <ha-icon icon="${icon}" style="color:${color}"></ha-icon>
      </span>`;
    } else {
      webAction = `<span class="action">
        <ha-icon icon="mdi:lock-open-variant" style="color:#43a047"></ha-icon>
      </span>`;
    }

    let lockAction;
    if (r.lockEnt && r.connType === "wifi") {
      const st = hass.states[r.lockEnt.entity_id];
      const locked = st && st.state === "locked";
      const icon = locked ? "mdi:close-circle" : "mdi:check-circle";
      const color = locked ? "#9e9e9e" : "#43a047";
      lockAction = `<span class="action" data-role="action" data-entity="${r.lockEnt.entity_id}" data-action="toggle-lock">
        <ha-icon icon="${icon}" style="color:${color}"></ha-icon>
      </span>`;
    } else {
      lockAction = `<span class="action"><ha-icon icon="mdi:minus" style="color:var(--secondary-text-color)"></ha-icon></span>`;
    }

    return `<div class="row" data-entity="${r.trackerId}">
      <ha-icon class="device-icon" icon="${this._esc(r.icon)}"></ha-icon>
      <span class="name">${this._esc(r.name)}</span>
      ${this._rateHtml(r.rxEnt, "down")}
      ${this._rateHtml(r.txEnt, "up")}
      ${webAction}
      ${lockAction}
    </div>`;
  }

  _fmtRate(ent) {
    if (!ent) return "–";
    const st = this._hass.states[ent.entity_id];
    if (!st || ["unknown", "unavailable"].includes(st.state)) return "–";
    return `${this._esc(st.state)} ${this._esc(st.attributes.unit_of_measurement || "")}`;
  }

  _webLabel(state) {
    return { allowed: "Autorisé", denied: "Bloqué", webonly: "Web uniquement" }[state] || state || "Autorisé";
  }

  /**
   * L'accès web est piloté au niveau du PROFIL de contrôle parental (pas
   * par appareil individuellement) : un profil couvre un ensemble de MAC.
   * Pour permettre un bouton "couper l'accès web" directement depuis cet
   * appareil, on retrouve le profil qui le couvre (via son MAC dans
   * l'attribut `macs` du sensor "État" de chaque profil), puis le select
   * "Mode" du même profil (même device_id) pour le basculer. Si l'appareil
   * n'est couvert par aucun profil, ou si son MAC est inconnu, retourne
   * null (le bouton est alors désactivé avec une explication).
   */
  _findProfileForMac(mac) {
    if (!mac || !this._hass.entities) return null;
    const macLower = String(mac).toLowerCase();
    const hass = this._hass;

    const profileSensors = Object.values(hass.entities).filter(
      (e) => e.platform === "freebox_devices" && /controle_parental_profil_\d+_etat$/.test(e.entity_id)
    );

    for (const ps of profileSensors) {
      const st = hass.states[ps.entity_id];
      const macs = (st && st.attributes && st.attributes.macs) || [];
      if (!macs.map((m) => String(m).toLowerCase()).includes(macLower)) continue;

      const siblings = Object.values(hass.entities).filter((e) => e.device_id === ps.device_id);
      const selectEnt = siblings.find((e) => e.entity_id.startsWith("select."));
      if (!selectEnt) continue;

      const device = hass.devices && hass.devices[ps.device_id];
      const deviceName = device ? device.name_by_user || device.name : null;

      return {
        selectId: selectEnt.entity_id,
        desc: deviceName,
        macsCount: macs.length,
      };
    }
    return null;
  }

  _renderDialogBody(row) {
    const hass = this._hass;
    const trackerState = hass.states[row.trackerId];
    const attrs = (trackerState && trackerState.attributes) || {};

    const connLabel = row.connType === "wifi" ? "Wifi" : row.connType === "ethernet" ? "Ethernet" : "Inconnu";
    const signalVal = row.sigEnt ? this._fmtRate(row.sigEnt) : null;

    const webState = row.webEnt ? hass.states[row.webEnt.entity_id] : null;
    const webStateVal = webState ? webState.state : "allowed";
    const webLabel = this._webLabel(webStateVal);
    const webColorMap = { allowed: "#43a047", denied: "#e53935", webonly: "#fb8c00" };
    const webColor = webColorMap[webStateVal] || "#43a047";

    const lockState = row.lockEnt ? hass.states[row.lockEnt.entity_id] : null;
    const locked = lockState && lockState.state === "locked";
    const canBlacklist = !!(row.lockEnt && row.connType === "wifi");

    const profile = this._findProfileForMac(row.mac);
    let webCutBtnHtml;
    if (profile) {
      const selectState = hass.states[profile.selectId];
      const currentOption = selectState ? selectState.state : null;
      const isBlocked = currentOption === "Toujours bloqué";
      const targetOption = isBlocked ? "Planning (automatique)" : "Toujours bloqué";
      const warning =
        profile.macsCount > 1
          ? `<div class="dialog-warning">⚠️ Ce profil${profile.desc ? " (" + this._esc(profile.desc) + ")" : ""} couvre ${profile.macsCount} appareils : cette action affecte aussi les autres.</div>`
          : "";
      webCutBtnHtml = `
        <button
          class="dialog-btn ${isBlocked ? "success" : "danger"}"
          data-role="select-option"
          data-entity="${profile.selectId}"
          data-option="${this._esc(targetOption)}"
        >
          ${isBlocked ? "Rétablir l'accès web" : "Couper l'accès web"}
        </button>
        ${warning}
      `;
    } else {
      webCutBtnHtml = `
        <button class="dialog-btn neutral" disabled>Couper l'accès web</button>
        <div class="dialog-hint">Aucun profil de contrôle parental ne couvre cet appareil pour l'instant — impossible de couper son accès web individuellement (créez/étendez un profil depuis la vue Profils).</div>
      `;
    }

    this._dialogBody.innerHTML = `
      <div class="dialog-section">
        <h4>État</h4>
        <div class="stat-grid">
          <div class="stat-item"><div class="label">Connexion</div><div class="value">${connLabel}</div></div>
          <div class="stat-item"><div class="label">IP</div><div class="value">${this._esc(attrs.ip || "–")}</div></div>
          ${signalVal ? `<div class="stat-item"><div class="label">Signal Wifi</div><div class="value">${signalVal}</div></div>` : ""}
          <div class="stat-item"><div class="label">Constructeur</div><div class="value">${this._esc(attrs.vendor || "Inconnu")}</div></div>
        </div>
      </div>

      <div class="dialog-section">
        <h4>Débit</h4>
        <div class="stat-grid">
          <div class="stat-item"><div class="label">↓ Descendant</div><div class="value">${this._fmtRate(row.rxEnt)}</div></div>
          <div class="stat-item"><div class="label">↑ Montant</div><div class="value">${this._fmtRate(row.txEnt)}</div></div>
        </div>
      </div>

      <div class="dialog-section">
        <h4>Historique de connexion</h4>
        <div class="history-list">Chargement…</div>
      </div>

      <div class="dialog-section">
        <h4>Accès internet</h4>
        <div class="stat-item">
          <div class="label">Accès web (via profil de contrôle parental)</div>
          <div class="value" style="color:${webColor}">${webLabel}</div>
        </div>
        ${webCutBtnHtml}
        <button class="dialog-btn neutral" data-role="goto-profils" data-path="/dashboard-freebox/profils">
          Voir les profils de contrôle parental
        </button>

        <button
          class="dialog-btn ${locked ? "success" : "danger"}"
          data-role="toggle-lock"
          data-entity="${row.lockEnt ? row.lockEnt.entity_id : ""}"
          ${canBlacklist ? "" : "disabled"}
        >
          ${locked ? "Débloquer l'accès Wifi" : "Bloquer l'accès Wifi (blacklist)"}
        </button>
        ${canBlacklist ? "" : `<div class="dialog-hint">Pas applicable : appareil non connecté en Wifi (le filtre Freebox n'agit que sur le Wifi).</div>`}
      </div>
    `;
  }

  async _loadHistory(trackerId) {
    if (!this._hass) return;
    const listEl = this.shadowRoot.querySelector(".history-list");
    try {
      // Fenêtre courte (48h) : empiriquement, l'endpoint history/period de
      // cette instance HA renvoie un tableau vide dès que `from` dépasse
      // ~1-2 jours en arrière pour ces entités récentes (constaté en testant
      // 1 à 7 jours en arrière : seul 1 jour renvoie des résultats), plutôt
      // qu'une rétention recorder plus large mal exploitée par une fenêtre
      // trop grande. 48h reste largement suffisant pour "l'historique
      // récent" demandé.
      const from = new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString();
      const path = `history/period/${from}?filter_entity_id=${encodeURIComponent(trackerId)}&minimal_response`;
      const data = await this._hass.callApi("GET", path);
      if (this._activeDialogTrackerId !== trackerId) return;

      const series = Array.isArray(data) && data.length ? data[0] : [];
      const items = series
        .slice()
        .reverse()
        .slice(0, 12)
        .map((entry) => {
          const stateLabel = entry.state === "home" ? "Connecté" : entry.state === "not_home" ? "Déconnecté" : entry.state;
          const cls = entry.state === "home" ? "home" : "not_home";
          const when = new Date(entry.last_changed).toLocaleString("fr-FR", {
            day: "2-digit",
            month: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          });
          return `<div class="history-item"><span class="state ${cls}">${this._esc(stateLabel)}</span><span>${this._esc(when)}</span></div>`;
        });

      const freshListEl = this.shadowRoot.querySelector(".history-list");
      if (!freshListEl) return;
      freshListEl.innerHTML = items.length
        ? items.join("")
        : `<div class="dialog-hint">Aucun historique récent</div>`;
    } catch (err) {
      const freshListEl = this.shadowRoot.querySelector(".history-list");
      if (freshListEl) freshListEl.innerHTML = `<div class="dialog-hint">Historique indisponible</div>`;
    }
  }
}

customElements.define("freebox-table-card", FreeboxTableCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "freebox-table-card",
  name: "Freebox — Liste appareils",
  description: "Liste des appareils connectés (débit ↓/↑, accès web, blacklist) avec écran de détail par appareil (stats, historique, actions), inclus avec l'intégration Freebox Devices.",
});
