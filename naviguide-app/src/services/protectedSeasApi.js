/**
 * NAVIGUIDE — ProtectedSeas Navigator V2 API client
 *
 * Toutes les requêtes passent par le proxy backend (/proxy/ps/{path})
 * qui ajoute le bon User-Agent et les headers CORS.
 *
 * RÈGLES CRITIQUES :
 * - Utiliser exclusivement ps_id (pas site_id, déprécié)
 * - Toujours passer export_bounds=true dans fetchSitesInRegion
 * - Gérer 404 et withheld en retournant null (pas de retry)
 */

import { PS_API_BASE } from '../constants/protectedSeasConfig.js';

/* ── Helpers ───────────────────────────────────────────────────────────────── */

/**
 * Calcule le centroïde d'un site à partir de ses bounds, en gérant plusieurs
 * formats de réponse de l'API PS (latitude/longitude null fréquent).
 *
 * @param {Object} site — objet site brut de l'API
 * @returns {{ lat: number, lng: number } | null}
 */
export function computeSiteCentroid(site) {
  // Cas 1 : lat/lon directement disponibles
  if (site.latitude != null && site.longitude != null) {
    const lat = parseFloat(site.latitude);
    const lng = parseFloat(site.longitude);
    if (!isNaN(lat) && !isNaN(lng)) return { lat, lng };
  }

  // Cas 2 : bounds imbriqué {min_lat, max_lat, min_lng, max_lng}
  const b = site.bounds || site.bbox;
  if (b) {
    if (typeof b === 'object' && !Array.isArray(b)) {
      const minLat = b.min_lat ?? b.min_latitude ?? b.south;
      const maxLat = b.max_lat ?? b.max_latitude ?? b.north;
      const minLng = b.min_lng ?? b.min_longitude ?? b.west;
      const maxLng = b.max_lng ?? b.max_longitude ?? b.east;
      if (minLat != null && maxLat != null && minLng != null && maxLng != null) {
        return {
          lat: (parseFloat(minLat) + parseFloat(maxLat)) / 2,
          lng: (parseFloat(minLng) + parseFloat(maxLng)) / 2,
        };
      }
    }
    // Cas 3 : bounds = [minLng, minLat, maxLng, maxLat]
    if (Array.isArray(b) && b.length === 4) {
      return { lat: (b[1] + b[3]) / 2, lng: (b[0] + b[2]) / 2 };
    }
  }

  // Cas 4 : propriétés à plat sur l'objet site
  const minLat = site.min_lat ?? site.min_latitude;
  const maxLat = site.max_lat ?? site.max_latitude;
  const minLng = site.min_lng ?? site.min_longitude;
  const maxLng = site.max_lng ?? site.max_longitude;
  if (minLat != null && maxLat != null && minLng != null && maxLng != null) {
    return {
      lat: (parseFloat(minLat) + parseFloat(maxLat)) / 2,
      lng: (parseFloat(minLng) + parseFloat(maxLng)) / 2,
    };
  }

  return null;
}

/* ── Fonctions API ─────────────────────────────────────────────────────────── */

/**
 * Récupère la liste des régions ProtectedSeas.
 * Chargé une seule fois au démarrage du composant.
 *
 * @returns {Promise<Array>}
 */
export async function fetchRegions() {
  const res = await fetch(`${PS_API_BASE}/regions/`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`PS regions HTTP ${res.status}`);
  const data = await res.json();
  if (Array.isArray(data)) return data;
  if (data?.results) return data.results;
  if (data?.features) return data.features.map((f) => f.properties ?? f);
  return [];
}

/**
 * Récupère les sites d'une région dans le viewport courant.
 *
 * IMPORTANT : export_bounds=true est TOUJOURS envoyé pour obtenir les bounds
 * des sites (nécessaires pour calculer le centroïde quand lat/lon est null).
 *
 * @param {string|number} regionId
 * @param {{ minLat, maxLat, minLng, maxLng }} bounds — viewport courant
 * @returns {Promise<Array>}
 */
export async function fetchSitesInRegion(regionId, bounds) {
  const params = new URLSearchParams({
    region_id: regionId,
    export_bounds: 'true',   // CRITIQUE — toujours présent
    page_size: '2000',        // max pour éviter la pagination
  });

  if (bounds) {
    if (bounds.minLat != null) params.set('lat_min', bounds.minLat.toFixed(6));
    if (bounds.maxLat != null) params.set('lat_max', bounds.maxLat.toFixed(6));
    if (bounds.minLng != null) params.set('lng_min', bounds.minLng.toFixed(6));
    if (bounds.maxLng != null) params.set('lng_max', bounds.maxLng.toFixed(6));
  }

  const res = await fetch(`${PS_API_BASE}/sites/?${params}`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`PS sites HTTP ${res.status}`);
  const data = await res.json();
  if (Array.isArray(data)) return data;
  if (data?.results) return data.results;
  if (data?.features) return data.features.map((f) => ({ ...f.properties, ...f }));
  return [];
}

/**
 * Récupère le polygone de limite d'un site par son ps_id.
 *
 * RÈGLES :
 * - Retourne null si 404 (géométrie withheld ou inconnue)
 * - Retourne null si le champ withheld est true
 * - NE PAS re-requêter si null (marquer comme traité côté composant)
 *
 * @param {string} ps_id
 * @returns {Promise<Object|null>} GeoJSON Feature ou null
 */
export async function fetchSiteBoundary(ps_id) {
  const res = await fetch(`${PS_API_BASE}/boundary/site/${ps_id}`, {
    headers: { Accept: 'application/json' },
  });

  if (res.status === 404) return null;

  if (!res.ok) {
    const err = new Error(`PS boundary HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }

  let data;
  try {
    data = await res.json();
  } catch {
    return null;
  }

  // Vérifier si withheld
  if (!data || data.withheld === true) return null;

  return data;
}

/**
 * Extrait la géométrie MapLibre-compatible depuis une réponse boundary.
 *
 * @param {Object} data — réponse brute de fetchSiteBoundary
 * @returns {Object|null} objet GeoJSON geometry ou null
 */
export function extractGeometry(data) {
  if (!data) return null;

  if (data.type === 'Feature') {
    return data.geometry ?? null;
  }
  if (data.type === 'FeatureCollection') {
    const geoms = (data.features ?? [])
      .map((f) => f.geometry)
      .filter(Boolean);
    if (geoms.length === 0) return null;
    if (geoms.length === 1) return geoms[0];
    // Fusion en MultiPolygon si plusieurs polygones
    const allCoords = [];
    for (const g of geoms) {
      if (g.type === 'Polygon') allCoords.push(g.coordinates);
      else if (g.type === 'MultiPolygon') allCoords.push(...g.coordinates);
    }
    return { type: 'MultiPolygon', coordinates: allCoords };
  }
  if (data.type === 'Polygon' || data.type === 'MultiPolygon') {
    return data;
  }
  if (data.geometry) return data.geometry;

  return null;
}
