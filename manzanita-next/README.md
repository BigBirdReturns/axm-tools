# Manzanita Works next: source foundation

The rejected v1.5.0 playtest proved that visual continuity without source continuity is a false product. This successor begins with a real place core and live source acquisition before rebuilding the public experience.

## Run locally

```bash
python -m pip install requests beautifulsoup4 pillow jsonschema pytest
cd manzanita-next
python -m scripts.acquire_foundation \
  --place config/place-demo.json \
  --registry config/source-registry.json \
  --out out
python scripts/validate_foundation.py \
  --root out \
  --source-schema contracts/source-envelope.schema.json
pytest -q tests
```

Optional credentials may be supplied as environment variables:

```text
GOOGLE_MAPS_API_KEY
MAPILLARY_ACCESS_TOKEN
AIRNOW_API_KEY
FIRMS_MAP_KEY
USGS_API_KEY
```

The current workflow intentionally does not use Google or Mapillary without configured credentials. Their absence produces explicit receipts rather than hidden mock data.
