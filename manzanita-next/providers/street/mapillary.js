export function mapillaryCoverageRequest({ accessToken, bbox, limit = 25 }) {
  const url = new URL("https://graph.mapillary.com/images");
  url.searchParams.set("access_token", accessToken || "");
  url.searchParams.set("bbox", bbox.join(","));
  url.searchParams.set(
    "fields",
    "id,computed_geometry,captured_at,compass_angle,thumb_1024_url"
  );
  url.searchParams.set("limit", String(limit));
  return {
    provider: "mapillary",
    available: Boolean(accessToken),
    method: "GET",
    url: url.toString(),
    cacheImagery: false,
    attributionRequired: true,
    failureReason: accessToken ? null : "MAPILLARY_ACCESS_TOKEN is not configured",
  };
}
