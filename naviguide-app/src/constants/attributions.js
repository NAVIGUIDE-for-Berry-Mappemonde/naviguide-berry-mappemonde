/**
 * NAVIGUIDE — Attribution table (single source of truth)
 *
 * Each entry describes ONE data provider surfaced by a map layer.
 * The MapAttribution component renders only entries whose layer is
 * currently active (toggle ON).
 *
 * `name`  : short label shown in the UI
 * `href`  : official website (opened in a new tab)
 * `year`  : optional publication year for academic citations
 */

export const ATTRIBUTIONS = {
  // Always active — base map tiles
  base: {
    name:  "© MapLibre demotiles",
    href:  "https://demotiles.maplibre.org",
  },
  // Marine Protected Areas
  mpas: {
    name:  "ProtectedSeas Navigator",
    citation: "Zetterlind et al., 2025",
    href:  "https://navigatormap.org",
  },
  // Exclusive Economic Zones
  eez: {
    name:  "VLIZ Marine Regions",
    href:  "https://www.marineregions.org",
  },
  // World Port Index
  ports: {
    name:  "NGA World Port Index",
    href:  "https://msi.nga.mil/Publications/WPI",
  },
  // Buoyage / seamark
  buoyage: {
    name:  "© OpenSeaMap contributors",
    href:  "https://www.openseamap.org",
  },
  // Blue Intelligence Projects
  projects: {
    name:  "Blue Intelligence Projects",
    href:  "https://www.blueintelligence.online",
  },
};
