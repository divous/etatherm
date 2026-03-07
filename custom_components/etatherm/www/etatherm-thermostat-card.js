/**
 * Etatherm Thermostat Card — custom Lovelace karta
 *
 * Zobrazuje:
 * - Naměřená teplota velkým uprostřed kruhu
 * - Cílová teplota menším pod ní
 * - Kruhový oblouk: modrá (pod cílem), zelená (na cíli), červená (nad cílem)
 * - +/- tlačítka pro změnu cílové teploty (→ aktivuje ROZ)
 * - Indikátor ROZ + tlačítko "Zpět na program" (jen když ROZ aktivní)
 */
class EtathermThermostatCard extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;
    this._render();
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Chybí 'entity'");
    this._config = config;
  }

  getCardSize() {
    return 4;
  }

  static getStubConfig() {
    return { entity: "climate.maja" };
  }

  _render() {
    const entity = this._hass.states[this._config.entity];
    if (!entity) {
      this.innerHTML = `<ha-card><div style="padding:16px">Entity not found: ${this._config.entity}</div></ha-card>`;
      return;
    }

    const name = this._config.name || entity.attributes.friendly_name || "";
    const current = entity.attributes.current_temperature;
    const target = entity.attributes.temperature;
    const hvacMode = entity.state; // "auto" or "heat"
    const isROZ = hvacMode === "heat";
    const hvacAction = entity.attributes.hvac_action || "idle";
    const isHeating = hvacAction === "heating";
    const minTemp = entity.attributes.min_temp || 6;
    const maxTemp = entity.attributes.max_temp || 35;

    // Barva oblouku
    let arcColor = "#4CAF50"; // zelená = na cíli
    let statusIcon = "✓";
    if (current !== null && target !== null) {
      if (current < target) {
        arcColor = "#42A5F5"; // modrá = pod cílem
        statusIcon = "❄";
      } else if (current > target) {
        arcColor = "#EF5350"; // červená = nad cílem
        statusIcon = "🔥";
      }
    }

    // Pozice oblouku (0-100%)
    const range = maxTemp - minTemp;
    const pct = current !== null ? Math.max(0, Math.min(100, ((current - minTemp) / range) * 100)) : 0;

    // SVG oblouk
    const startAngle = 135;
    const endAngle = 405;
    const totalArc = endAngle - startAngle;
    const angle = startAngle + (pct / 100) * totalArc;

    const r = 90;
    const cx = 110;
    const cy = 110;

    const toXY = (a) => ({
      x: cx + r * Math.cos((a * Math.PI) / 180),
      y: cy + r * Math.sin((a * Math.PI) / 180),
    });

    const bgStart = toXY(startAngle);
    const bgEnd = toXY(endAngle);
    const arcStart = toXY(startAngle);
    const arcEnd = toXY(angle);
    const largeArc = angle - startAngle > 180 ? 1 : 0;

    const bgPath = `M ${bgStart.x} ${bgStart.y} A ${r} ${r} 0 1 1 ${bgEnd.x} ${bgEnd.y}`;
    const arcPath = pct > 0
      ? `M ${arcStart.x} ${arcStart.y} A ${r} ${r} 0 ${largeArc} 1 ${arcEnd.x} ${arcEnd.y}`
      : "";

    // Pozice bodu na konci oblouku
    const dotPos = toXY(angle);

    // Indikátor ROZ nebo "dle programu"
    const statusBadge = isROZ
      ? `<span class="badge roz">ROZ aktivní</span>`
      : `<span class="badge auto">Dle programu</span>`;

    // Tlačítko "Zpět na program" jen když ROZ aktivní
    const autoButton = isROZ
      ? `<button class="auto-btn" id="btn-auto">Zpět na program</button>`
      : "";

    this.innerHTML = `
      <ha-card>
        <div class="card-content">
          <div class="header">
            <span class="name">${name.toUpperCase()}</span>
            ${statusBadge}
          </div>
          <div class="dial-container">
            <svg viewBox="0 0 220 200" class="dial">
              <path d="${bgPath}" fill="none" stroke="#e0e0e0" stroke-width="8" stroke-linecap="round"/>
              ${arcPath ? `<path d="${arcPath}" fill="none" stroke="${arcColor}" stroke-width="8" stroke-linecap="round"/>` : ""}
              ${pct > 0 ? `<circle cx="${dotPos.x}" cy="${dotPos.y}" r="6" fill="white" stroke="${arcColor}" stroke-width="3"/>` : ""}
            </svg>
            <div class="temp-display">
              <div class="current-temp">${current !== null ? current : "—"}<span class="unit">°C</span></div>
              <div class="target-temp">${statusIcon} → ${target !== null ? target + "°" : "—"}</div>
              <div class="heating-indicator ${isHeating ? 'active' : ''}">${isHeating ? '🔥 Topí' : '⏸ Netopí'}</div>
            </div>
          </div>
          <div class="controls">
            <button class="btn minus" id="btn-minus">−</button>
            <button class="btn plus" id="btn-plus">+</button>
          </div>
          ${autoButton}
        </div>
      </ha-card>
      <style>
        ha-card {
          padding: 0;
          overflow: hidden;
        }
        .card-content {
          padding: 20px 16px 16px;
          display: flex;
          flex-direction: column;
          align-items: center;
        }
        .header {
          width: 100%;
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 4px;
        }
        .name {
          font-weight: 600;
          font-size: 14px;
          letter-spacing: 0.5px;
          color: var(--primary-text-color);
        }
        .badge {
          font-size: 11px;
          font-weight: 600;
          padding: 3px 10px;
          border-radius: 12px;
        }
        .badge.auto {
          background: var(--green-color, #4CAF50);
          color: white;
        }
        .badge.roz {
          background: var(--red-color, #F44336);
          color: white;
        }
        .dial-container {
          position: relative;
          width: 220px;
          height: 190px;
        }
        .dial {
          width: 100%;
          height: 100%;
        }
        .temp-display {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -40%);
          text-align: center;
        }
        .current-temp {
          font-size: 48px;
          font-weight: 300;
          line-height: 1;
          color: var(--primary-text-color);
        }
        .current-temp .unit {
          font-size: 20px;
          vertical-align: super;
          margin-left: 2px;
        }
        .target-temp {
          font-size: 15px;
          color: var(--secondary-text-color);
          margin-top: 6px;
        }
        .heating-indicator {
          font-size: 12px;
          margin-top: 6px;
          color: var(--secondary-text-color);
          opacity: 0.7;
        }
        .heating-indicator.active {
          color: var(--red-color, #F44336);
          opacity: 1;
          animation: pulse 1.5s ease-in-out infinite;
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        .controls {
          display: flex;
          gap: 16px;
          margin: 8px 0 12px;
        }
        .btn {
          width: 48px;
          height: 48px;
          border-radius: 50%;
          border: 2px solid var(--divider-color, #e0e0e0);
          background: none;
          font-size: 22px;
          cursor: pointer;
          color: var(--primary-text-color);
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s;
        }
        .btn:active {
          background: var(--divider-color, #e0e0e0);
        }
        .auto-btn {
          width: 100%;
          padding: 10px 0;
          border: 2px solid var(--divider-color, #e0e0e0);
          border-radius: 12px;
          background: none;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          color: var(--secondary-text-color);
          transition: all 0.2s;
        }
        .auto-btn:hover {
          border-color: var(--primary-color, #03a9f4);
          color: var(--primary-text-color);
        }
        .auto-btn:active {
          background: var(--divider-color, #e0e0e0);
        }
      </style>
    `;

    // Event handlers
    this.querySelector("#btn-minus").addEventListener("click", () => {
      const newTemp = (target || 20) - 1;
      this._setTemperature(newTemp);
    });
    this.querySelector("#btn-plus").addEventListener("click", () => {
      const newTemp = (target || 20) + 1;
      this._setTemperature(newTemp);
    });
    const autoBtn = this.querySelector("#btn-auto");
    if (autoBtn) {
      autoBtn.addEventListener("click", () => {
        this._setMode("auto");
      });
    }
  }

  _setTemperature(temp) {
    this._hass.callService("climate", "set_temperature", {
      entity_id: this._config.entity,
      temperature: temp,
    });
  }

  _setMode(mode) {
    this._hass.callService("climate", "set_hvac_mode", {
      entity_id: this._config.entity,
      hvac_mode: mode,
    });
  }
}

customElements.define("etatherm-thermostat-card", EtathermThermostatCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "etatherm-thermostat-card",
  name: "Etatherm Thermostat",
  description: "Thermostat card with +/- controls, ROZ indicator, and Auto return button",
});
