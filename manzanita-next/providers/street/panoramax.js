export function panoramaxSearchRequest({ bbox, limit = 50 }) {
  return {
    provider: "panoramax",
    method: "POST",
    url: "https://api.panoramax.xyz/api/search",
    headers: { "content-type": "application/json" },
    body: { bbox, limit },
    attribution: "Panoramax federation and item-level contributors",
  };
}
