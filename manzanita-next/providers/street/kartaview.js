function slippyTile(latitude, longitude, zoom) {
  const clampedLatitude = Math.max(-85.05112878, Math.min(85.05112878, latitude));
  const n = 2 ** zoom;
  const x = Math.floor(((longitude + 180) / 360) * n);
  const radians = (clampedLatitude * Math.PI) / 180;
  const y = Math.floor(((1 - Math.asinh(Math.tan(radians)) / Math.PI) / 2) * n);
  return { x, y, zoom };
}

export function kartaViewCoverageRequest({ latitude, longitude, zoomLevel = 15 }) {
  const tile = slippyTile(latitude, longitude, zoomLevel);
  return {
    provider: "kartaview",
    assetClass: "coverage",
    method: "GET",
    url: `https://api.openstreetcam.org/2.0/sequence/tiles/${tile.x}/${tile.y}/${tile.zoom}.geojson`,
    attribution: "KartaView contributors",
  };
}

export function kartaViewNearbyRequest({ latitude, longitude, zoomLevel = 15 }) {
  const url = new URL("https://api.openstreetcam.org/2.0/photo/");
  url.searchParams.set("lat", String(latitude));
  url.searchParams.set("lng", String(longitude));
  url.searchParams.set("zoomLevel", String(zoomLevel));
  url.searchParams.set("join", "sequence");
  url.searchParams.set("orderBy", "id");
  url.searchParams.set("orderDirection", "desc");
  return {
    provider: "kartaview",
    assetClass: "nearby-photo-metadata",
    method: "GET",
    url: url.toString(),
    attribution: "KartaView contributors",
  };
}
