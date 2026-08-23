/**
 * MaritimeLayers — unified layer hub for MapLibre GL JS
 *
 * Layers rendered by this module (Sources/Layers in <Map>):
 *  1. ZEE         — Zones Économiques Exclusives (VLIZ / Marine Regions WFS proxy)
 *  2. Ports WPI   — World Port Index (NGA/MSI, backend proxy)
 *  3. Balisage    — Seamark raster tiles (OpenSeaMap, public)
 *
 * Layers rendered elsewhere but toggled from THIS panel (props flow through
 * `useMaritimeLayers` for a single source of truth):
 *  4. MPAs        — ProtectedSeas Navigator PMTiles (see ProtectedSeasLayer.jsx)
 *  5. Projects    — Blue Intelligence Projects points (see BlueProjectsLayer.jsx)
 *
 * The MPAs button carries a chevron `▾` that opens a compact popover listing
 * the 5 LFP protection levels with coloured pills. Filter state is `null`
 * (all LFPs shown) or `Set<number>` (subset).
 *
 * Exports:
 *  - useMaritimeLayers() → hook (toggle state + data)
 *  - MaritimeLayers(props) → Sources/Layers to place INSIDE <Map>
 *  - BalisageLayer(props) → seamark raster, place LAST inside <Map>
 *  - MaritimeLayersPanel(props) → floating pill bar with the 5 toggles
 */

import { useEffect, useRef, useState } from "react";
import { Source, Layer } from "react-map-gl/maplibre";
import { useLang } from "../i18n/LangContext.jsx";
import { LFP_COLORS, LFP_LABELS } from "../constants/protectedSeasConfig.js";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const EMPTY_FC = { type: "FeatureCollection", features: [] };

// ── Paint styles ─────────────────────────────────────────────────────────────

const ZEE_WMS_TILES = [
  `${API_BASE}/proxy/zee/wms?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&LAYERS=eez_boundaries&FORMAT=image/png&TRANSPARENT=true&SRS=EPSG:3857&WIDTH=512&HEIGHT=512&BBOX={bbox-epsg-3857}`,
];
const PORTS_CIRCLE_PAINT = {
  "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 2, 6, 4, 10, 7],
  "circle-color": "#f59e0b",
  "circle-stroke-width": 1,
  "circle-stroke-color": "#fff",
  "circle-opacity": 0.85,
};

// ── Fetchers ─────────────────────────────────────────────────────────────────

async function fetchPorts() {
  const url = `${API_BASE}/proxy/ports`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Ports HTTP ${res.status}`);
  return res.json();
}

// ── Hook ─────────────────────────────────────────────────────────────────────

/**
 * useMaritimeLayers
 * All layer toggles + data fetching for the 5 map layers.
 *
 * Defaults:
 *   ZEE=on, Ports=on, Buoyage=on, MPAs=off, Projects=off, lfpFilter=null (all)
 */
export function useMaritimeLayers() {
  const [showZee,      setShowZee]      = useState(true);
  const [showPorts,    setShowPorts]    = useState(true);
  const [showBalisage, setShowBalisage] = useState(true);
  const [showMpas,     setShowMpas]     = useState(false);
  const [showProjects, setShowProjects] = useState(false);

  // MPA LFP filter — null = all shown, Set<number> = subset
  const [lfpFilter,    setLfpFilter]    = useState(null);

  const [portsData,     setPortsData]    = useState(EMPTY_FC);
  const [loadingPorts,  setLoadingPorts] = useState(false);
  const [errorPorts,    setErrorPorts]   = useState(null);

  useEffect(() => {
    if (!showPorts || portsData.features.length > 0) return;
    setLoadingPorts(true);
    setErrorPorts(null);
    fetchPorts()
      .then((data) => { setPortsData(data); })
      .catch((e) => { console.warn("[MaritimeLayers] Ports:", e.message || e); setErrorPorts(e.message || String(e)); })
      .finally(() => setLoadingPorts(false));
  }, [showPorts]);

  return {
    // Toggles
    showZee,      setShowZee,
    showPorts,    setShowPorts,
    showBalisage, setShowBalisage,
    showMpas,     setShowMpas,
    showProjects, setShowProjects,
    // MPA LFP filter
    lfpFilter,    setLfpFilter,
    // Data
    portsData,
    // Loading
    loadingZee:      false,
    loadingPorts,
    loadingBalisage: false,
    loadingMpas:     false,
    loadingProjects: false,
    // Errors
    errorZee:      null,
    errorPorts,
    errorBalisage: null,
    errorMpas:     null,
    errorProjects: null,
  };
}

// ── Map layers (inside <Map>) ────────────────────────────────────────────────

export function MaritimeLayers({ showZee, showPorts, portsData, showBalisage }) {
  const vis = (flag) => ({ visibility: flag ? "visible" : "none" });

  return (
    <>
      <Source
        id="zee-source"
        type="raster"
        tiles={ZEE_WMS_TILES}
        tileSize={512}
        minzoom={1}
        maxzoom={18}
      >
        <Layer
          id="zee-layer"
          type="raster"
          layout={vis(showZee)}
          paint={{
            "raster-opacity": ["interpolate", ["linear"], ["zoom"], 1, 0.25, 3, 0.45, 6, 0.7, 10, 0.9],
            "raster-fade-duration": 0,
            "raster-resampling": "nearest",
          }}
        />
      </Source>

      <Source id="ports-source" type="geojson" data={portsData}>
        <Layer id="ports-circle" type="circle" layout={vis(showPorts)} paint={PORTS_CIRCLE_PAINT} />
      </Source>
    </>
  );
}

/** Seamark raster — place LAST inside <Map> (renders above routes/markers). */
const SEAMARK_TILES = [
  `${API_BASE}/proxy/seamark/{z}/{x}/{y}.png`,
  "https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png",
];

export function BalisageLayer({ show }) {
  return (
    <Source
      id="openseamap-source"
      type="raster"
      tiles={SEAMARK_TILES}
      tileSize={256}
      minzoom={1}
      maxzoom={19}
    >
      <Layer
        id="openseamap-layer"
        type="raster"
        layout={{ visibility: show ? "visible" : "none" }}
        paint={{ "raster-opacity": 1, "raster-fade-duration": 0 }}
      />
    </Source>
  );
}

// ── Toggle panel (outside <Map>) ─────────────────────────────────────────────

/**
 * Layer config — declarative order for the pill bar.
 * `hasPopover` triggers a chevron button next to the pill.
 */
const LAYER_CONFIG = [
  { key: "zee",      labelKey: "layerZee",      titleKey: "layerZeeTitle",      color: "#0e7490", showKey: "showZee",      toggleKey: "setShowZee",      loadingKey: "loadingZee",      errorKey: "errorZee"     },
  { key: "ports",    labelKey: "layerPorts",    titleKey: "layerPortsTitle",    color: "#f59e0b", showKey: "showPorts",    toggleKey: "setShowPorts",    loadingKey: "loadingPorts",    errorKey: "errorPorts"   },
  { key: "balisage", labelKey: "layerBalisage", titleKey: "layerBalisageTitle", color: "#10b981", showKey: "showBalisage", toggleKey: "setShowBalisage", loadingKey: "loadingBalisage", errorKey: "errorBalisage"},
  { key: "mpas",     labelKey: "layerMpas",     titleKey: "layerMpasTitle",     color: "#22c55e", showKey: "showMpas",     toggleKey: "setShowMpas",     loadingKey: "loadingMpas",     errorKey: "errorMpas",  hasPopover: true },
  { key: "projects", labelKey: "layerProjects", titleKey: "layerProjectsTitle", color: "#14b8a6", showKey: "showProjects", toggleKey: "setShowProjects", loadingKey: "loadingProjects", errorKey: "errorProjects"},
];

/**
 * LFP Popover — 5 protection levels (5..1) with coloured pills.
 * Positioned above the MPAs button (bottom-full + mb-2).
 */
function LfpPopover({ lfpFilter, setLfpFilter, onClose, t }) {
  const rootRef = useRef(null);
  const lang = t("_lang");

  // Close on Escape + outside click
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    const onDown = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) onClose();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [onClose]);

  const toggleLevel = (lvl) => {
    if (lfpFilter === null) {
      // moving from "all" to "subset": exclude this level
      const next = new Set([5, 4, 3, 2, 1]);
      next.delete(lvl);
      setLfpFilter(next.size === 5 ? null : next);
    } else {
      const next = new Set(lfpFilter);
      if (next.has(lvl)) next.delete(lvl); else next.add(lvl);
      setLfpFilter(next.size === 5 ? null : next);
    }
  };

  return (
    <div
      ref={rootRef}
      role="dialog"
      aria-label={t("ampLfpLegend")}
      className="absolute bottom-full mb-2 right-0 min-w-[180px] z-30
                 bg-slate-900/95 backdrop-blur-md border border-white/15
                 rounded-xl shadow-2xl px-3 py-2.5"
    >
      <div className="text-[9px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
        {t("ampLfpLegend")}
      </div>
      <div className="space-y-1">
        {[5, 4, 3, 2, 1].map((lvl) => {
          const isActive = lfpFilter === null || lfpFilter.has(lvl);
          return (
            <button
              key={lvl}
              onClick={() => toggleLevel(lvl)}
              className={[
                "flex items-center gap-2 w-full rounded-lg px-2 py-1 transition-all",
                "text-[11px] text-left focus:outline-none focus:ring-1 focus:ring-white/40",
                isActive
                  ? "bg-slate-700/50 text-white"
                  : "bg-transparent text-slate-500 hover:text-slate-400",
              ].join(" ")}
            >
              <div
                className="w-2.5 h-2.5 rounded-sm flex-shrink-0 transition-opacity"
                style={{ backgroundColor: LFP_COLORS[lvl], opacity: isActive ? 1 : 0.25 }}
              />
              <span className={isActive ? "" : "line-through"}>
                {(LFP_LABELS[lang] ?? LFP_LABELS.en)[lvl]}
              </span>
              {isActive && (
                <span className="ml-auto text-slate-500 text-[8px]">✓</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function MaritimeLayersPanel(props) {
  const { t } = useLang();
  const [lfpOpen, setLfpOpen] = useState(false);

  // Split layers into 2 rows: 3 on top, 2 below (MPAs on bottom-left keeps
  // its chevron for LFP filter). Widths are 3-col grid; MPAs is 1 col, but
  // its chevron sits INSIDE the same button cell → we let the cell size
  // adapt via flex.
  const rowTop    = LAYER_CONFIG.slice(0, 3);
  const rowBottom = LAYER_CONFIG.slice(3);   // MPAs + Projects

  return (
    <div
      className="grid grid-cols-3 gap-1.5 mt-2.5"
      style={{ pointerEvents: "auto" }}
    >
      {rowTop.map((cfg) => (
        <PillCell
          key={cfg.key}
          cfg={cfg}
          props={props}
          lfpOpen={lfpOpen}
          setLfpOpen={setLfpOpen}
          t={t}
        />
      ))}
      {/* Row 2: MPAs (1 col) + Projects (2 cols wide) */}
      {rowBottom.map((cfg, i) => (
        <div
          key={cfg.key}
          className={i === rowBottom.length - 1 ? "col-span-2" : ""}
        >
          <PillCell
            cfg={cfg}
            props={props}
            lfpOpen={lfpOpen}
            setLfpOpen={setLfpOpen}
            t={t}
            fullWidth
          />
        </div>
      ))}
    </div>
  );
}

/**
 * PillCell — one toggle pill (+ optional chevron popover).
 * `fullWidth` stretches the pill to fill its grid cell.
 */
function PillCell({ cfg, props, lfpOpen, setLfpOpen, t, fullWidth = false }) {
  const { key, labelKey, titleKey, color, showKey, toggleKey, loadingKey, errorKey, hasPopover } = cfg;
  const active  = props[showKey];
  const loading = props[loadingKey];
  const error   = props[errorKey];
  const isMpas  = key === "mpas";
  const widthCls = fullWidth ? "w-full" : "";

  return (
    <div className="relative flex items-center">
      <button
        onClick={() => props[toggleKey]((v) => !v)}
        title={t(titleKey)}
        className={[
          "flex items-center justify-center gap-1 px-2 py-1 text-[10px] font-semibold",
          "transition-all duration-150 select-none",
          hasPopover ? "rounded-l-full flex-1" : `rounded-full ${widthCls}`,
          active
            ? "bg-slate-700/90 text-white border border-white/20"
            : "bg-transparent text-white/45 border border-white/10 hover:text-white/80 hover:bg-slate-700/50",
          error ? "border-red-500/50" : "",
        ].join(" ")}
      >
        {loading ? (
          <div className="w-1.5 h-1.5 rounded-full border-2 border-white/30 border-t-white animate-spin flex-shrink-0" />
        ) : (
          <div
            className="w-1.5 h-1.5 rounded-full flex-shrink-0 transition-colors"
            style={{
              backgroundColor: active ? color : "transparent",
              border: `1.5px solid ${error ? "#ef4444" : color}`,
            }}
          />
        )}
        <span>{t(labelKey)}</span>
        {error && !loading && (
          <span className="text-red-400 text-[10px]" title={error}>⚠</span>
        )}
      </button>

      {hasPopover && (
        <>
          <button
            onClick={() => setLfpOpen((v) => !v)}
            title={t("ampLfpLegend")}
            aria-expanded={lfpOpen}
            aria-haspopup="dialog"
            className={[
              "flex items-center justify-center px-1.5 py-1 rounded-r-full text-[10px]",
              "border-l-0 transition-all duration-150 select-none",
              active
                ? "bg-slate-700/90 text-white border border-white/20"
                : "bg-transparent text-white/45 border border-white/10 hover:text-white/80 hover:bg-slate-700/50",
            ].join(" ")}
          >
            <span aria-hidden="true">{lfpOpen ? "▴" : "▾"}</span>
          </button>

          {isMpas && lfpOpen && (
            <LfpPopover
              lfpFilter={props.lfpFilter}
              setLfpFilter={props.setLfpFilter}
              onClose={() => setLfpOpen(false)}
              t={t}
            />
          )}
        </>
      )}
    </div>
  );
}
