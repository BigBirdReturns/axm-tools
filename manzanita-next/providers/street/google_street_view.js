export function createGoogleStreetViewDescriptor({ apiKeyPresent, position, radiusMeters = 75 }) {
  return {
    provider: "google_street_view",
    available: Boolean(apiKeyPresent),
    position,
    radiusMeters,
    runtimeOnly: true,
    cacheImagery: false,
    attributionRequired: true,
    failureReason: apiKeyPresent ? null : "GOOGLE_MAPS_API_KEY is not configured",
  };
}
