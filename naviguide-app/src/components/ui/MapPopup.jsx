/**
 * MapPopup — unified popup shell for MapLibre
 * --------------------------------------------
 * Wraps react-map-gl <Popup> with a consistent white-background design used
 * by all map popups (Satellite Data, MPA, Blue Intelligence Project, etc).
 *
 * Design rules (per product decision, 2026-08):
 *  - Pure `bg-white` (no transparency, no blur), text `text-slate-800`.
 *  - `rounded-xl` corners, `shadow-xl`, thin slate border for lift.
 *  - Optional 4-px `accentColor` bar at the top (purely decorative).
 *  - Header row: title + close (X) — close-on-click is disabled on the
 *    underlying <Popup> so the user has to hit X.
 *  - Body is scrollable if it grows past 60vh.
 *  - Native MapLibre popup close button hidden — we render our own.
 *  - MapLibre chooses the anchor automatically to stay in-viewport.
 *
 * Usage:
 *   <MapPopup lng={..} lat={..} title="Wind" accentColor="#3b82f6" onClose={..}>
 *     ...body...
 *   </MapPopup>
 */

import { Popup } from "react-map-gl/maplibre";
import { X } from "lucide-react";

export function MapPopup({
  lng,
  lat,
  title,
  accentColor,
  onClose,
  maxWidth = 400,
  children,
}) {
  return (
    <Popup
      longitude={lng}
      latitude={lat}
      onClose={onClose}
      closeOnClick={false}
      closeButton={false}
      anchor="auto"
      maxWidth={`${maxWidth}px`}
      className="naviguide-popup"
    >
      <div
        className="bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden"
        style={{ minWidth: 280, maxWidth: maxWidth }}
      >
        {accentColor && (
          <div
            className="h-1 w-full"
            style={{ backgroundColor: accentColor }}
            aria-hidden="true"
          />
        )}

        {(title || onClose) && (
          <div className="flex items-start gap-2 px-3.5 pt-3 pb-1.5">
            {title && (
              <h3 className="flex-1 text-sm font-semibold text-slate-800 leading-tight m-0">
                {title}
              </h3>
            )}
            {onClose && (
              <button
                onClick={onClose}
                aria-label="Close popup"
                className="shrink-0 -mt-0.5 -mr-1 p-0.5 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              >
                <X size={14} strokeWidth={2.5} />
              </button>
            )}
          </div>
        )}

        <div className="px-3.5 pb-3 pt-1 text-slate-700 text-xs max-h-[60vh] overflow-y-auto">
          {children}
        </div>
      </div>
    </Popup>
  );
}
