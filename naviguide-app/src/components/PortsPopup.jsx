/**
 * PortsPopup — WPI (World Port Index) minimal popup.
 * Shows only the port name + country per product decision.
 * Data source: NGA/MSI WPI GeoJSON served via /api/proxy/ports.
 */
import { MapPopup } from "./ui/MapPopup.jsx";
import { useLang } from "../i18n/LangContext.jsx";

const PORTS_COLOR = "#f59e0b"; // amber-500 — same as the WPI dot layer

export function PortsPopup({ port, onClose }) {
  const { t } = useLang();
  if (!port) return null;

  // MapLibre may hand properties back as a JSON string on clustered vector
  // sources. WPI is a plain GeoJSON source so it is always an object here,
  // but we defensively normalise to match the pattern used elsewhere.
  let p = port.properties ?? {};
  if (typeof p === "string") {
    try { p = JSON.parse(p); } catch { p = {}; }
  }

  return (
    <MapPopup
      lng={port.lng}
      lat={port.lat}
      title={p.name || t("portUnnamed")}
      accentColor={PORTS_COLOR}
      onClose={onClose}
      maxWidth={280}
      data-testid="ports-popup"
    >
      <div className="space-y-1.5">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-500">
            {t("portName")}
          </div>
          <div className="text-sm font-semibold text-slate-800">
            {p.name || "—"}
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-500">
            {t("portCountry")}
          </div>
          <div className="text-sm text-slate-700">
            {p.country || "—"}
          </div>
        </div>
      </div>
    </MapPopup>
  );
}
