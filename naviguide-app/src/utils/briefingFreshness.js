/**
 * formatBriefingFreshness
 *
 * Given an ISO-8601 `generatedAt` and TTL seconds, return a locale-friendly
 * string like "Généré le 23/08/2026 à 21:31 · Rafraîchir dans 22h" or
 * "Generated 23/08/2026 at 21:31 · Refresh in 22h".
 *
 * Returns null if metadata is missing / invalid so the caller can hide the row.
 */
export function formatBriefingFreshness({ generatedAt, ttlSeconds, lang, t }) {
  if (!generatedAt || !Number.isFinite(ttlSeconds) || ttlSeconds <= 0) return null;

  const genDate = new Date(generatedAt);
  if (Number.isNaN(genDate.getTime())) return null;

  const expiresMs = genDate.getTime() + ttlSeconds * 1000;
  const remainingMs = expiresMs - Date.now();

  // Date part — 24h notation, zero-padded.
  const dd = String(genDate.getDate()).padStart(2, "0");
  const mm = String(genDate.getMonth() + 1).padStart(2, "0");
  const yyyy = genDate.getFullYear();
  const HH = String(genDate.getHours()).padStart(2, "0");
  const MM = String(genDate.getMinutes()).padStart(2, "0");
  const dateStr = lang === "fr"
    ? `${dd}/${mm}/${yyyy} à ${HH}:${MM}`
    : `${dd}/${mm}/${yyyy} at ${HH}:${MM}`;

  // Remaining part — coarse-grained (minutes / hours / days).
  let remainingStr;
  if (remainingMs <= 0) {
    remainingStr = t("briefingExpired");
  } else {
    const totalMinutes = Math.floor(remainingMs / 60000);
    const days  = Math.floor(totalMinutes / (60 * 24));
    const hours = Math.floor(totalMinutes / 60);
    const mins  = totalMinutes % 60;
    if (days >= 1) {
      remainingStr = lang === "fr" ? `${days}j` : `${days}d`;
    } else if (hours >= 1) {
      remainingStr = `${hours}h`;
    } else {
      remainingStr = lang === "fr" ? `${mins} min` : `${mins} min`;
    }
    remainingStr = t("briefingRefreshIn").replace("{{remaining}}", remainingStr);
  }

  return t("briefingFreshness")
    .replace("{{date}}", dateStr)
    .replace("{{remaining}}", remainingStr);
}
