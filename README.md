# Fuel Route API

A Django REST API that takes a start and finish location in the USA and returns
the driving route, the cost-optimal places to fuel up along the way, and the
total estimated fuel cost.

Assumptions (per the brief): vehicle range **500 miles**, fuel economy
**10 miles per gallon**. Fuel prices come from the provided CSV.

---

## Stack

| Concern | Tool |
|---|---|
| Framework | Django 5.x + Django REST Framework |
| Database | PostgreSQL 16 |
| Server | Gunicorn |
| Routing | OSRM (free, no key needed) |
| Geocoding | Nominatim / OpenStreetMap (free, no key needed) |
| Map tiles | OpenStreetMap via Leaflet.js |
| Fuel data | Provided CSV (~8,000 US truck stops) |

### External API usage

The brief asks for as few calls to the map/routing API as possible. Per request
we make **exactly three** external calls: two Nominatim geocodes (origin and
destination) and **one** OSRM call for the route. Fuel-stop selection then runs
entirely against the local database — no extra map calls.

---

## Running with Docker

```bash
# 1. Enter the project
cd fuel_route_api

# 2. Copy environment file (defaults work out of the box)
cp .env.example .env

# 3. Start everything
docker compose up --build -d

# 4. Watch logs
docker compose logs -f web
```

The API is then available at **http://localhost:8000**.

On first boot the entrypoint waits for Postgres, runs migrations, seeds the
tunable constants (`init_constants`), imports the CSV (`import_fuel_stations
--skip-existing`), and starts Gunicorn.

---

## API Reference

### `POST /api/route/`

**Request:**
```json
{
  "origin": "Chicago, IL",
  "destination": "Houston, TX"
}
```

**Response `200 OK`:**
```json
{
  "origin": { "input": "Chicago, IL", "display_name": "...", "lat": 41.85, "lon": -87.65 },
  "destination": { "input": "Houston, TX", "display_name": "...", "lat": 29.76, "lon": -95.37 },
  "route": {
    "distance_miles": 1083.4,
    "duration_hours": 15.8,
    "duration_formatted": "15h 48m",
    "polyline": { "type": "LineString", "coordinates": [[...]] }
  },
  "fuel_stops": [
    {
      "stop_number": 1,
      "station_name": "PILOT TRAVEL CENTER #412",
      "address": "I-55, EXIT 160 & US-51",
      "city": "Bloomington",
      "state": "IL",
      "price_per_gallon": 2.899,
      "miles_from_start": 541.7,
      "gallons_to_fill": 54.17,
      "cost_at_stop": 157.04
    }
  ],
  "cost_summary": {
    "total_distance_miles": 1083.4,
    "total_gallons_needed": 108.34,
    "miles_per_gallon": 10,
    "vehicle_range_miles": 500,
    "estimated_total_fuel_cost_usd": 314.08
  },
  "map": {
    "center": { "lat": 35.8, "lon": -91.2 },
    "markers": [...],
    "route_polyline": [[...]],
    "leaflet_tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "leaflet_attribution": "© OpenStreetMap contributors"
  }
}
```

**Error responses:**

| Status | Reason |
|---|---|
| `400` | Missing `origin` or `destination` |
| `422` | Location not found or unroutable |
| `500` | Unexpected server error |

### `GET /api/route/`

Returns the API schema as JSON.

---

## Fuel Stop Selection

Truck-stop coordinates are not available, so stops are chosen by **state** rather
than by precise geolocation:

1. Take the bounding box of the OSRM route polyline.
2. Pick every US state whose bounding box overlaps it (static table in
   `apps/routing/utils.py` — no extra API calls).
3. Query the cheapest stations in those states:
   `FuelStation.objects.filter(state__in=route_states).order_by("retail_price")`.
4. With a 500-mile range, the number of stops is
   `ceil(total_distance / 500) - 1`. Select that many of the cheapest stations,
   spread evenly along the route, and total the fuel cost.

Map markers for the stops are placed at the proportional point along the route
polyline (since the stations themselves have no coordinates).

> Trade-off: the route bounding box is rectangular, so for long east–west trips
> it can include states the route only grazes. This keeps selection fast and
> map-call-free at the cost of some geographic precision.

---

## Configuration

Tunable constants live in the `AppConstants` key/value table (`core` app) and are
seeded by `init_constants`. They can be edited in the Django admin without a
redeploy; the planner reads them per request.

| Key | Default |
|---|---|
| `vehicle_range_miles` | 500 |
| `miles_per_gallon` | 10 |
| `default_fuel_price` | 3.50 |
| `nominatim_url` | https://nominatim.openstreetmap.org/search |
| `osrm_route_url` | https://router.project-osrm.org/route/v1/driving |
| `user_agent` | FuelRouteAPI/1.0 |

---

## Management Commands

```bash
# Seed/refresh the constants (idempotent; --reset to overwrite)
docker compose exec web python manage.py init_constants

# Import the CSV (wipes and reloads; --skip-existing to no-op if populated)
docker compose exec web python manage.py import_fuel_stations
```

---

## Project Structure

```
fuel_route_api/
├── config/
│   ├── settings.py          # config via environment variables
│   ├── urls.py
│   └── wsgi.py / asgi.py
├── apps/
│   ├── core/
│   │   ├── models.py        # AppConstants key/value store
│   │   └── management/commands/init_constants.py
│   └── routing/
│       ├── models.py        # FuelStation
│       ├── utils.py         # geocode, state bounds, helpers
│       ├── services/
│       │   └── route_planner.py   # RoutePlanner (class-based)
│       ├── views.py         # thin DRF views
│       ├── urls.py
│       ├── fuel_prices.csv
│       └── management/commands/import_fuel_stations.py
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh            # wait for DB → migrate → seed → import → serve
├── .env.example
└── requirements.txt
```
