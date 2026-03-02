/**
 * useMarkerOffsets
 * Calcule des décalages pixel pour éviter le chevauchement des markers MapLibre.
 *
 * Algorithme (itératif, convergence garantie) :
 *  1. Projette chaque point en coordonnées écran via map.project()
 *  2. Itère jusqu'à MAX_ITERATIONS en appliquant des vecteurs de répulsion
 *     calculés sur les positions ACCUMULÉES (pas juste les positions de base).
 *     Cela garantit que même 3+ markers groupés convergent vers une position
 *     sans chevauchement.
 *  3. Stoppe dès que la plus grande correction d'une itération < MIN_PUSH px.
 *  4. Recompute à chaque fin de zoom ou de déplacement (debounced).
 *
 * Usage :
 *   const offsets = useMarkerOffsets(points, mapRef);
 *   // offsets[i] → [dx, dy] en pixels pour le marker i
 *   <Marker offset={offsets[i]} ... />
 */

import { useState, useEffect, useCallback, useRef } from "react";

// Drapeaux : 36×26 px → diagonale ~44 px. On prend 56 px pour avoir une marge
// confortable même quand deux drapeaux se touchent par un coin.
const OVERLAP_THRESHOLD = 56; // px — séparation minimale entre centres
const MAX_ITERATIONS    = 20; // itérations max de l'algorithme de répulsion
const MIN_PUSH          = 0.4; // px — arrêt anticipé si toutes corrections < seuil
const DEBOUNCE_MS       = 120;

export function useMarkerOffsets(points, mapRef) {
  const [offsets, setOffsets] = useState(() => points.map(() => [0, 0]));
  const timerRef = useRef(null);

  const compute = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (!map || !points.length) return;

    // ── 1. Projection en pixels écran (positions de base, sans offset) ────────
    const base = points.map((p) => {
      const pt = map.project([p.lon, p.lat]);
      return [pt.x, pt.y];
    });

    // ── 2. Algorithme de répulsion itératif ───────────────────────────────────
    // result[i] = offset accumulé du marker i (commence à [0, 0])
    const result = points.map(() => [0, 0]);

    for (let iter = 0; iter < MAX_ITERATIONS; iter++) {
      let maxPush = 0; // amplitude max de cette itération

      for (let i = 0; i < points.length; i++) {
        for (let j = i + 1; j < points.length; j++) {
          // Position courante (base + offset accumulé)
          const ax = base[i][0] + result[i][0];
          const ay = base[i][1] + result[i][1];
          const bx = base[j][0] + result[j][0];
          const by = base[j][1] + result[j][1];

          const dx   = bx - ax;
          const dy   = by - ay;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < OVERLAP_THRESHOLD && dist > 0.5) {
            // Chaque marker reçoit la moitié de la pénétration + marge
            const push = (OVERLAP_THRESHOLD - dist) / 2 + 2;
            const nx = dx / dist;
            const ny = dy / dist;

            result[i][0] -= nx * push;
            result[i][1] -= ny * push;
            result[j][0] += nx * push;
            result[j][1] += ny * push;

            if (push > maxPush) maxPush = push;
          }
        }
      }

      // Convergence atteinte : aucune paire ne se chevauchait significativement
      if (maxPush < MIN_PUSH) break;
    }

    setOffsets(result);
  }, [points, mapRef]);

  // ── Debounced recompute on map move/zoom ──────────────────────────────────
  useEffect(() => {
    if (!points.length) return;

    const schedule = () => {
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(compute, DEBOUNCE_MS);
    };

    // Attend que la carte soit chargée avant d'accrocher les events
    const attachListeners = () => {
      const map = mapRef.current?.getMap();
      if (!map) return false;
      map.on("zoomend", schedule);
      map.on("moveend", schedule);
      compute(); // calcul initial
      return true;
    };

    // Polling léger tant que la carte n'est pas prête
    if (!attachListeners()) {
      const poll = setInterval(() => {
        if (attachListeners()) clearInterval(poll);
      }, 200);
      return () => {
        clearInterval(poll);
        clearTimeout(timerRef.current);
      };
    }

    return () => {
      clearTimeout(timerRef.current);
      const map = mapRef.current?.getMap();
      if (map) {
        map.off("zoomend", schedule);
        map.off("moveend", schedule);
      }
    };
  }, [compute, mapRef, points]);

  return offsets;
}
