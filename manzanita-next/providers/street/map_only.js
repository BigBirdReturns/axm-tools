export function mapOnlyDescriptor({ reason, geometryAvailable = true }) {
  return {
    provider: "map_only",
    available: true,
    geometryAvailable,
    reason: reason || "No qualified street imagery is available for the requested place.",
    imageryClaim: "none",
  };
}
