/**
 * NAVIGUIDE — ProtectedSeas Navigator V2 configuration
 *
 * Data source: public PMTiles on S3, fetched directly by MapLibre via
 * byte-range requests (pmtiles:// protocol).  No backend proxy needed.
 *
 * Each lfpN_boundaries.pmtiles exposes a vector layer "lfpN" with properties:
 *   SITE_ID    String  — unique PS identifier, e.g. "AIAG1"
 *   SITE_NAME  String  — human-readable name
 *   LFP        Number  — Level of Fishing Protection 0–5
 *   COMMERCIAL Number  — commercial fishing restriction 0–3
 *   ARTISANAL_ Number  — artisanal fishing restriction 0–3
 *   RECREATION Number  — recreation restriction 0–3
 *   SPEED      Number  — speed restriction 0–3
 *   DESIGNATION String — legal designation type
 *   OBJECTID   Number  — internal id, used for Navigator permalink
 */

/** S3 base for public ProtectedSeas PMTiles */
export const PS_S3_BASE =
  'https://s3.us-west-2.amazonaws.com/pmtiles.navigator.protectedseas';

/** Navigator site permalink — append ?pin=OBJECTID */
export const PS_NAVIGATOR_URL = 'https://map.navigatormap.org/v2/areas';

/** Fill/line color per LFP level (1–5) */
export const LFP_COLORS = {
  5: '#ef4444', // Red    — Very high protection
  4: '#f97316', // Orange — High protection
  3: '#eab308', // Yellow — Moderate protection
  2: '#38bdf8', // Sky    — Low protection
  1: '#1e40af', // Navy   — Minimal protection
};

/** Human-readable LFP labels per language */
export const LFP_LABELS = {
  fr: {
    5: 'LFP 5 — Très haute',
    4: 'LFP 4 — Haute',
    3: 'LFP 3 — Modérée',
    2: 'LFP 2 — Faible',
    1: 'LFP 1 — Minimale',
  },
  en: {
    5: 'LFP 5 — Very High',
    4: 'LFP 4 — High',
    3: 'LFP 3 — Moderate',
    2: 'LFP 2 — Low',
    1: 'LFP 1 — Minimal',
  },
};

/**
 * Restriction score display (COMMERCIAL, ARTISANAL_, RECREATION, SPEED).
 * 0 = allowed, 1 = limited, 2 = regulated, 3 = prohibited
 */
export const RESTRICTION_ICONS = { 0: '✅', 1: '🟡', 2: '🟠', 3: '🚫' };
export const RESTRICTION_LABELS = {
  fr: { 0: 'Autorisé', 1: 'Limité', 2: 'Réglementé', 3: 'Interdit' },
  en: { 0: 'Allowed',  1: 'Limited', 2: 'Regulated',  3: 'Prohibited' },
};

/** Minimum zoom level before AMP layers are rendered */
export const ZOOM_THRESHOLD = 6;

/** Mandatory attribution strings */
export const PS_ATTRIBUTION_EN =
  'MPAs: ProtectedSeas Navigator Map of Conservation Regulations. Zetterlind et al. (2025). navigatormap.org';
export const PS_ATTRIBUTION_FR =
  'AMP : ProtectedSeas Navigator. Zetterlind et al. (2025). navigatormap.org';
