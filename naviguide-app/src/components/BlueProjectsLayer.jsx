/**
 * BlueProjectsLayer
 * ------------------
 * Renders the Blue Intelligence Projects layer (~4465 Points worldwide).
 *
 * Design choices (documented for reviewer):
 *  - Data: fetched lazily from /data/blue_intelligence_projects.geojson only
 *    when the toggle first activates. Cached in state afterwards.
 *  - Rendering: native MapLibre `circle` layer (GPU-accelerated) with
 *    `cluster: true` on the Source. HTML markers would freeze the browser
 *    with 4465 points.
 *  - Colour: turquoise `#14b8a6` — distinct from ports (`#f59e0b`),
 *    catamaran flag/waypoints, ZEE, MPAs (LFP palette).
 *  - Cluster style: darker turquoise with white count label, radius scales
 *    with point count.
 *  - Interaction: click on unclustered point opens a Popup with title,
 *    category badge, description (truncated), funder, and a "See project"
 *    hyperlink.
 *  - Default: OFF (parent App owns the toggle state).
 */

import { useEffect, useState } from "react";
import { Source, Layer, Popup } from "react-map-gl/maplibre";
import { useLang } from "../i18n/LangContext.jsx";

const EMPTY_FC = { type: "FeatureCollection", features: [] };
const DATA_URL = "/data/blue_intelligence_projects.geojson";

const PROJECTS_COLOR   = "#14b8a6";   // teal-500 (turquoise)
const PROJECTS_DARKER  = "#0d9488";   // teal-600

const UNCLUSTERED_PAINT = {
  "circle-color":         PROJECTS_COLOR,
  "circle-radius":        ["interpolate", ["linear"], ["zoom"], 1, 3, 6, 5, 12, 8],
  "circle-stroke-width":  1.5,
  "circle-stroke-color":  "#ffffff",
  "circle-opacity":       0.9,
};

const CLUSTER_PAINT = {
  "circle-color": [
    "step", ["get", "point_count"],
    PROJECTS_COLOR,    50,
    PROJECTS_DARKER,  200,
    "#115e59",
  ],
  "circle-radius": [
    "step", ["get", "point_count"],
    12,  50,
    18, 200,
    24,
  ],
  "circle-opacity":       0.85,
  "circle-stroke-width":  2,
  "circle-stroke-color":  "#ffffff",
};

const CLUSTER_COUNT_LAYOUT = {
  "text-field":  ["get", "point_count_abbreviated"],
  "text-size":   11,
  "text-font":   ["Noto Sans Regular"],
};

const CLUSTER_COUNT_PAINT = { "text-color": "#ffffff" };

/**
 * Hook: fetches the GeoJSON lazily. Returns {data, loading, error}.
 */
export function useBlueProjectsData(show) {
  const [data,    setData]    = useState(EMPTY_FC);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    if (!show || data.features.length > 0 || loading) return;
    setLoading(true);
    setError(null);
    fetch(DATA_URL)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((gj) => setData(gj))
      .catch((e) => {
        console.warn("[BlueProjects] fetch failed:", e);
        setError(e.message || String(e));
      })
      .finally(() => setLoading(false));
  }, [show]);

  return { data, loading, error };
}

/**
 * Map layers — mount inside <Map>.
 * Uses `layout.visibility` to toggle without unmount side-effects.
 */
export function BlueProjectsLayer({ show, data, onFeatureClick }) {
  const vis = show ? "visible" : "none";
  return (
    <Source
      id="blue-projects-src"
      type="geojson"
      data={data}
      cluster={true}
      clusterRadius={50}
      clusterMaxZoom={7}
    >
      <Layer
        id="blue-projects-clusters"
        type="circle"
        filter={["has", "point_count"]}
        layout={{ visibility: vis }}
        paint={CLUSTER_PAINT}
      />
      <Layer
        id="blue-projects-cluster-count"
        type="symbol"
        filter={["has", "point_count"]}
        layout={{ ...CLUSTER_COUNT_LAYOUT, visibility: vis }}
        paint={CLUSTER_COUNT_PAINT}
      />
      <Layer
        id="blue-projects-points"
        type="circle"
        filter={["!", ["has", "point_count"]]}
        layout={{ visibility: vis }}
        paint={UNCLUSTERED_PAINT}
      />
    </Source>
  );
}

/**
 * Popup component — controlled from App.jsx (uses state).
 * Props: { feature: {lng, lat, properties}, onClose }.
 */
export function BlueProjectsPopup({ feature, onClose }) {
  const { t } = useLang();
  if (!feature) return null;
  const p = feature.properties || {};
  const desc = (p.description || "").trim();
  const shortDesc = desc.length > 260 ? desc.slice(0, 257) + "…" : desc;

  return (
    <Popup
      longitude={feature.lng}
      latitude={feature.lat}
      onClose={onClose}
      closeOnClick={false}
      anchor="top"
      maxWidth="320px"
    >
      <div className="text-slate-800">
        <div className="font-semibold text-sm mb-1 leading-tight">{p.title || "Project"}</div>
        {p.category && (
          <div className="inline-block bg-teal-100 text-teal-800 text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide mb-1.5">
            {p.category}
          </div>
        )}
        {shortDesc && (
          <p className="text-xs text-slate-600 leading-snug mb-1.5">{shortDesc}</p>
        )}
        {p.funder && (
          <div className="text-[11px] text-slate-500 mb-1">
            <span className="font-medium">Funder :</span> {p.funder}
          </div>
        )}
        {p.url && (
          <a
            href={p.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-teal-700 hover:text-teal-900 text-xs font-medium underline underline-offset-2"
          >
            {t("projectsSeeMore") || "See project ↗"}
          </a>
        )}
      </div>
    </Popup>
  );
}
