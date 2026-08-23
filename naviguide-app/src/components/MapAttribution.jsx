/**
 * MapAttribution
 * ---------------
 * Unified, dynamic attribution footer for the MapLibre map.
 * Renders in the bottom-right corner. Shows ONE entry per currently-active
 * layer. Base map is always shown first.
 *
 * Replaces:
 *   - MapLibre native AttributionControl (disabled via `attributionControl={false}`)
 *   - Legacy "© OpenSeaMap | ProtectedSeas Navigator | MapLibre" footer
 *   - Duplicate MPA citation formerly shown under the LFP popover
 *
 * Props: which layers are ON.
 */

import { ATTRIBUTIONS } from "../constants/attributions.js";

export function MapAttribution({
  showEez = false,
  showPorts = false,
  showBuoyage = false,
  showMpas = false,
  showProjects = false,
}) {
  // Base always first
  const active = [ATTRIBUTIONS.base];
  if (showMpas)     active.push(ATTRIBUTIONS.mpas);
  if (showEez)      active.push(ATTRIBUTIONS.eez);
  if (showPorts)    active.push(ATTRIBUTIONS.ports);
  if (showBuoyage)  active.push(ATTRIBUTIONS.buoyage);
  if (showProjects) active.push(ATTRIBUTIONS.projects);

  return (
    <div
      className="absolute bottom-1.5 right-1.5 z-20 pointer-events-auto
                 bg-slate-900/70 backdrop-blur-sm rounded px-2 py-1
                 text-[10px] text-white/70 leading-tight
                 max-w-[70vw] text-right"
      role="contentinfo"
      aria-label="Map data attribution"
    >
      {active.map((entry, i) => (
        <span key={entry.href}>
          {i > 0 && <span className="text-white/30 mx-1.5" aria-hidden="true">·</span>}
          <a
            href={entry.href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-white/85 hover:text-white underline decoration-white/30 hover:decoration-white/70 decoration-1 underline-offset-2"
          >
            {entry.name}
          </a>
          {entry.citation && (
            <span className="text-white/55"> ({entry.citation})</span>
          )}
        </span>
      ))}
    </div>
  );
}
