export const STREET_PROVIDER_ORDER = [
  "google_street_view",
  "mapillary",
  "kartaview",
  "panoramax",
  "owned_capture",
  "map_only",
];

export function rankCandidates(candidates, now = Date.now()) {
  const order = new Map(STREET_PROVIDER_ORDER.map((id, index) => [id, index]));
  return [...candidates]
    .filter((candidate) => candidate && candidate.available)
    .sort((a, b) => {
      const providerDelta = (order.get(a.provider) ?? 99) - (order.get(b.provider) ?? 99);
      if (providerDelta !== 0) return providerDelta;
      const aAge = a.capturedAt ? now - Date.parse(a.capturedAt) : Number.POSITIVE_INFINITY;
      const bAge = b.capturedAt ? now - Date.parse(b.capturedAt) : Number.POSITIVE_INFINITY;
      if (aAge !== bAge) return aAge - bAge;
      return (a.distanceMeters ?? Number.POSITIVE_INFINITY) - (b.distanceMeters ?? Number.POSITIVE_INFINITY);
    });
}

export function selectStreetScene(candidates) {
  const ranked = rankCandidates(candidates);
  return ranked[0] ?? {
    provider: "map_only",
    available: true,
    reason: "No qualified street imagery is available for the requested place.",
  };
}
