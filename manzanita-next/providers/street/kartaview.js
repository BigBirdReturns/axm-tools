export function kartaViewNearbyRequest({ latitude, longitude, radiusMeters = 1200 }) {
  const url = new URL("https://api.openstreetcam.org/2.0/photo/");
  url.searchParams.set("lat", String(latitude));
  url.searchParams.set("lng", String(longitude));
  url.searchParams.set("radius", String(radiusMeters));
  return {
    provider: "kartaview",
    method: "GET",
    url: url.toString(),
    attribution: "KartaView contributors",
  };
}
