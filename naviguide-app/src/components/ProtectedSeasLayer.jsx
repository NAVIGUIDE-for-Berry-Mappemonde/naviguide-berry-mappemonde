/**
 * NAVIGUIDE — ProtectedSeasLayer
 * Marine Protected Areas via ProtectedSeas Navigator V2 PMTiles.
 *
 * Architecture:
 *  - Data: 5 public S3 PMTiles (one per LFP level), accessed directly by
 *    MapLibre via byte-range requests — NO backend proxy required.
 *  - Protocol: pmtiles:// registered once globally via maplibre-gl addProtocol.
 *  - Each lfpN_boundaries.pmtiles contains a vector layer "lfpN" with full
 *    feature properties: SITE_NAME, SITE_ID, LFP, COMMERCIAL, ARTISANAL_,
 *    RECREATION, DESIGNATION, OBJECTID.
 *  - Click popup reads properties directly from the rendered vector feature.
 */

import { useEffect, useState } from 'react';
import { Source, Layer } from 'react-map-gl/maplibre';
import maplibregl from 'maplibre-gl';
import { Protocol } from 'pmtiles';
import { useLang } from '../i18n/LangContext.jsx';
import { MapPopup } from './ui/MapPopup.jsx';
import {
  PS_S3_BASE,
  PS_NAVIGATOR_URL,
  LFP_COLORS,
  LFP_LABELS,
  RESTRICTION_ICONS,
  RESTRICTION_LABELS,
  ZOOM_THRESHOLD,
} from '../constants/protectedSeasConfig';

// ── PMTiles protocol registration (global, idempotent) ────────────────────────
let _pmtilesRegistered = false;
function ensurePMTilesProtocol() {
  if (_pmtilesRegistered) return;
  const protocol = new Protocol();
  maplibregl.addProtocol('pmtiles', protocol.tile);
  _pmtilesRegistered = true;
}

// ── LFP levels ────────────────────────────────────────────────────────────────
const LFP_LEVELS = [1, 2, 3, 4, 5];

// ── Restriction badge sub-component ──────────────────────────────────────────
function RestrictionRow({ value, label, lang }) {
  if (typeof value !== 'number') return null;
  const v = Math.min(3, Math.max(0, Math.round(value)));
  const icon  = RESTRICTION_ICONS[v];
  const text  = RESTRICTION_LABELS[lang]?.[v] ?? '';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 2 }}>
      <span style={{ fontSize: 12 }}>{icon}</span>
      <span style={{ fontSize: 11, color: '#374151' }}>
        <strong>{label}</strong> — {text}
      </span>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
/**
 * @param {{ mapRef: React.MutableRefObject, showAMP: boolean, lfpFilter: Set<number>|null }} props
 */
export function ProtectedSeasLayer({ mapRef, showAMP, lfpFilter }) {
  const { lang, t } = useLang();
  const [popup, setPopup]       = useState(null);   // { lng, lat, props, lfpN }
  const [currentZoom, setZoom]  = useState(0);

  // Register PMTiles protocol once on mount
  useEffect(() => {
    ensurePMTilesProtocol();
  }, []);

  // Track map zoom for threshold gating
  useEffect(() => {
    const map = mapRef?.current?.getMap?.();
    if (!map) return;
    const onZoom = () => setZoom(map.getZoom());
    map.on('zoom', onZoom);
    setZoom(map.getZoom());
    return () => { map.off('zoom', onZoom); };
  }, [mapRef]);

  // Click and hover event handlers
  useEffect(() => {
    const map = mapRef?.current?.getMap?.();
    if (!map || !showAMP) return;

    const fillIds = LFP_LEVELS.map(n => `ps-fill-${n}`);

    const getActiveLayers = () =>
      fillIds.filter(id => { try { return !!map.getLayer(id); } catch { return false; } });

    const handleClick = (e) => {
      const active = getActiveLayers();
      if (!active.length) return;
      const features = map.queryRenderedFeatures(e.point, { layers: active });
      if (features.length > 0) {
        const f = features[0];
        // Extract the LFP level from the layer id (ps-fill-N)
        const lfpN = parseInt(f.layer.id.replace('ps-fill-', ''), 10) || 1;
        setPopup({ lng: e.lngLat.lng, lat: e.lngLat.lat, props: f.properties, lfpN });
      } else {
        setPopup(null);
      }
    };

    const handleMouseMove = (e) => {
      const active = getActiveLayers();
      if (!active.length) return;
      const features = map.queryRenderedFeatures(e.point, { layers: active });
      map.getCanvas().style.cursor = features.length > 0 ? 'pointer' : '';
    };

    map.on('click', handleClick);
    map.on('mousemove', handleMouseMove);
    return () => {
      map.off('click', handleClick);
      map.off('mousemove', handleMouseMove);
      try { map.getCanvas().style.cursor = ''; } catch { /* map unmounted */ }
    };
  }, [mapRef, showAMP]);

  // Gate: nothing to render when hidden or zoomed out
  if (!showAMP || currentZoom < ZOOM_THRESHOLD) return null;

  return (
    <>
      {LFP_LEVELS.map(n => {
        const visible = (!lfpFilter || lfpFilter.has(n)) ? 'visible' : 'none';
        const color   = LFP_COLORS[n];

        const fillSpec = {
          id: `ps-fill-${n}`,
          type: 'fill',
          'source-layer': `lfp${n}`,
          layout: { visibility: visible },
          paint: { 'fill-color': color, 'fill-opacity': 0.22 },
        };
        const lineSpec = {
          id: `ps-line-${n}`,
          type: 'line',
          'source-layer': `lfp${n}`,
          layout: { visibility: visible },
          paint: {
            'line-color': color,
            'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.8, 10, 1.8, 14, 2.5],
            'line-opacity': 0.85,
          },
        };

        return (
          <Source
            key={`ps-src-${n}`}
            id={`ps-${n}`}
            type="vector"
            url={`pmtiles://${PS_S3_BASE}/lfp${n}_boundaries.pmtiles`}
            attribution="ProtectedSeas Navigator"
          >
            <Layer {...fillSpec} />
            <Layer {...lineSpec} />
          </Source>
        );
      })}

      {popup && (
        <MapPopup
          lng={popup.lng}
          lat={popup.lat}
          title={popup.props?.SITE_NAME?.trim() || t('ampUnnamed')}
          accentColor={LFP_COLORS[popup.props?.LFP ?? popup.lfpN]}
          onClose={() => setPopup(null)}
          maxWidth={320}
        >
          {/* LFP badge */}
          <div
            style={{
              display: 'inline-flex', alignItems: 'center',
              background: LFP_COLORS[popup.props?.LFP ?? popup.lfpN],
              color: '#fff', borderRadius: 4,
              padding: '2px 8px', fontSize: 11, fontWeight: 600, marginBottom: 8,
            }}
          >
            {LFP_LABELS[lang]?.[popup.props?.LFP ?? popup.lfpN]
              ?? `LFP ${popup.props?.LFP ?? popup.lfpN}`}
          </div>

          {/* Designation */}
          {popup.props?.DESIGNATION?.trim?.() && (
            <div className="text-[10px] text-slate-500 italic leading-snug mb-2">
              {popup.props.DESIGNATION.trim()}
            </div>
          )}

          {/* Restrictions */}
          <div className="mb-2">
            <RestrictionRow
              value={popup.props?.COMMERCIAL}
              label={lang === 'fr' ? 'Pêche commerciale' : 'Commercial fishing'}
              lang={lang}
            />
            <RestrictionRow
              value={popup.props?.ARTISANAL_}
              label={lang === 'fr' ? 'Pêche artisanale' : 'Artisanal fishing'}
              lang={lang}
            />
            <RestrictionRow
              value={popup.props?.RECREATION}
              label={lang === 'fr' ? 'Activités récréatives' : 'Recreation'}
              lang={lang}
            />
            <RestrictionRow
              value={popup.props?.SPEED}
              label={lang === 'fr' ? 'Vitesse' : 'Speed'}
              lang={lang}
            />
          </div>

          {/* Navigator link */}
          {popup.props?.OBJECTID && (
            <a
              href={`${PS_NAVIGATOR_URL}?pin=${popup.props.OBJECTID}`}
              target="_blank"
              rel="noopener noreferrer"
              className="block text-[11px] text-blue-600 hover:text-blue-800 border-t border-slate-200 pt-1.5 mt-1"
            >
              {t('ampSeeNavigator')} ↗
            </a>
          )}
        </MapPopup>
      )}
    </>
  );
}
