/**
 * WavePopup / CurrentPopup
 *
 * Small wrappers around the shared MapPopup shell that render the two
 * Copernicus-driven popups (waves & currents) previously duplicated inline
 * in App.jsx. Same shell, same close-button, same anchor-auto logic — the
 * only difference between the two is the accent color and the fields shown.
 *
 * Props:
 *   state    — { longitude, latitude, data?, error? }  (same shape as before)
 *   loading  — bool (spinner state)
 *   onClose  — () => void
 */
import { MapPopup } from "./ui/MapPopup.jsx";
import { useLang } from "../i18n/LangContext.jsx";

const WAVE_COLOR    = "#f97316"; // orange-500 — was the header gradient
const CURRENT_COLOR = "#22c55e"; // green-500  — was the header gradient

function Spinner({ color }) {
  return (
    <div className="flex flex-col items-center py-5">
      <div
        className="w-8 h-8 border-4 rounded-full animate-spin"
        style={{ borderColor: `${color}22`, borderTopColor: color }}
      />
      <div className="mt-3 text-slate-500 text-sm">Loading…</div>
    </div>
  );
}

function ErrorRow({ message }) {
  return (
    <div className="flex items-center gap-3 p-3 bg-red-50 border border-red-200 rounded-lg">
      <span className="text-xl" aria-hidden="true">⚠️</span>
      <div className="text-red-600 text-sm">{message}</div>
    </div>
  );
}

function DataRow({ icon, label, value }) {
  return (
    <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 bg-white rounded-md flex items-center justify-center text-lg" aria-hidden="true">
          {icon}
        </div>
        <div>
          <div className="text-xs text-slate-500 mb-0.5">{label}</div>
          <div className="text-base font-semibold text-slate-800">{value}</div>
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────

export function WavePopup({ state, loading, onClose }) {
  const { t } = useLang();
  if (!state) return null;
  const d = state.data;

  return (
    <MapPopup
      lng={state.longitude}
      lat={state.latitude}
      title={t("wavePopupTitle")}
      accentColor={WAVE_COLOR}
      onClose={onClose}
      maxWidth={280}
      data-testid="wave-popup"
    >
      {loading ? (
        <Spinner color={WAVE_COLOR} />
      ) : state.error ? (
        <ErrorRow message={state.error} />
      ) : d ? (
        <div className="space-y-3">
          <DataRow icon="🌊" label={t("waveHeight")}    value={`${d.significant_wave_height_m} m`} />
          {d.mean_wave_period    && <DataRow icon="⏱️" label={t("wavePeriod")}    value={`${d.mean_wave_period} s`} />}
          {d.mean_wave_direction && <DataRow icon="🧭" label={t("waveDirection")} value={`${d.mean_wave_direction}°`} />}
        </div>
      ) : (
        <div className="py-5 text-center text-slate-500 text-sm">{t("noData")}</div>
      )}
    </MapPopup>
  );
}

// ────────────────────────────────────────────────────────────────────────────

export function CurrentPopup({ state, loading, onClose }) {
  const { t } = useLang();
  if (!state) return null;
  const d = state.data;

  return (
    <MapPopup
      lng={state.longitude}
      lat={state.latitude}
      title={t("currentPopupTitle")}
      accentColor={CURRENT_COLOR}
      onClose={onClose}
      maxWidth={280}
      data-testid="current-popup"
    >
      {loading ? (
        <Spinner color={CURRENT_COLOR} />
      ) : state.error ? (
        <ErrorRow message={state.error} />
      ) : d ? (
        <div className="space-y-3">
          <DataRow icon="🌊" label={t("currentSpeedLabel")}     value={`${d.speed_knots.toFixed(2)} kn`} />
          {d.direction_deg != null && (
            <DataRow icon="🧭" label={t("currentDirectionLabel")} value={`${d.direction_deg.toFixed(1)}°`} />
          )}
        </div>
      ) : (
        <div className="py-5 text-center text-slate-500 text-sm">{t("noData")}</div>
      )}
    </MapPopup>
  );
}
