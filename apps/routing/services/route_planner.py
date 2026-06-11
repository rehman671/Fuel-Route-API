import math

import requests
from django.db import models as django_models

from apps.core.models import AppConstants
from apps.routing.models import FuelStation
from apps.routing.utils import format_duration, geocode, states_in_bbox


class RoutePlanner:
    CONSTANT_KEYS = [
        "vehicle_range_miles",
        "miles_per_gallon",
        "default_fuel_price",
        "nominatim_url",
        "osrm_route_url",
        "user_agent",
    ]

    def __init__(self):
        c = dict(
            AppConstants.objects.filter(key__in=self.CONSTANT_KEYS)
            .values_list("key", "value")
        )

        self.vehicle_range_miles = int(float(c["vehicle_range_miles"]))
        self.mpg = float(c["miles_per_gallon"])
        self.default_fuel_price = float(c["default_fuel_price"])
        self.nominatim_url = c["nominatim_url"]
        self.osrm_route_url = c["osrm_route_url"]
        self.user_agent = c["user_agent"]

    @property
    def gallon_per_mile(self):
        return 1.0 / self.mpg

    @property
    def headers(self):
        return {"User-Agent": self.user_agent}

    def geocode(self, location):
        return geocode(location, self.nominatim_url, self.user_agent)

    def get_osrm_route(self, lat1, lon1, lat2, lon2):
        url = f"{self.osrm_route_url}/{lon1},{lat1};{lon2},{lat2}"
        params = {"overview": "full", "geometries": "geojson", "steps": "false"}
        resp = requests.get(url, params=params, headers=self.headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != "Ok":
            raise ValueError(f"OSRM error: {data.get('message', 'unknown')}")

        route = data["routes"][0]
        return {
            "distance_miles": round(route["distance"] / 1609.344, 2),
            "duration_seconds": int(route["duration"]),
            "coordinates": route["geometry"]["coordinates"],
        }

    def plan_fuel_stops(self, route_coords, total_distance_miles):
        # Fits in a single tank, no stops required
        if total_distance_miles <= self.vehicle_range_miles:
            return []

        # Stations in any state the route's bounding box touches, cheapest first
        route_states = states_in_bbox(route_coords)
        stations = list(
            FuelStation.objects.filter(state__in=route_states).order_by("retail_price")
        )
        if not stations:
            return []

        # One stop per tank boundary; pick the cheapest distinct stations
        num_stops = math.ceil(total_distance_miles / self.vehicle_range_miles) - 1
        chosen = stations[:num_stops]
        leg_miles = total_distance_miles / (len(chosen) + 1)
        gallons_per_leg = round(leg_miles * self.gallon_per_mile, 2)

        stops = []
        for i, station in enumerate(chosen, start=1):
            price = float(station.retail_price)
            stops.append({
                "stop_number": i,
                "station_name": station.name,
                "address": station.address,
                "city": station.city,
                "state": station.state,
                "price_per_gallon": price,
                "miles_from_start": round(leg_miles * i, 2),
                "gallons_to_fill": gallons_per_leg,
                "cost_at_stop": round(gallons_per_leg * price, 2),
            })
        return stops

    def calculate_total_fuel_cost(self, total_distance_miles, fuel_stops):
        total_gallons = round(total_distance_miles * self.gallon_per_mile, 2)

        if fuel_stops:
            # Stops cover every leg after the first; the first leg is fuelled at
            # the origin, estimated at the cheapest stop's price.
            stop_costs = sum(s["cost_at_stop"] for s in fuel_stops)
            first = fuel_stops[0]
            first_leg_cost = round(first["gallons_to_fill"] * first["price_per_gallon"], 2)
            total_cost = round(stop_costs + first_leg_cost, 2)
        else:
            avg_price = float(
                FuelStation.objects.aggregate(avg=django_models.Avg("retail_price"))["avg"]
                or self.default_fuel_price
            )
            total_cost = round(total_gallons * avg_price, 2)

        return {
            "total_distance_miles": round(total_distance_miles, 2),
            "total_gallons_needed": total_gallons,
            "miles_per_gallon": self.mpg,
            "vehicle_range_miles": self.vehicle_range_miles,
            "estimated_total_fuel_cost_usd": total_cost,
        }

    def build_map_data(self, origin_geo, dest_geo, route_coords, fuel_stops):
        markers = [
            {"type": "origin", "label": "Start", "name": origin_geo["display_name"].split(",")[0], "lat": round(origin_geo["lat"], 6), "lon": round(origin_geo["lon"], 6), "icon": "green"},
            {"type": "destination", "label": "End", "name": dest_geo["display_name"].split(",")[0], "lat": round(dest_geo["lat"], 6), "lon": round(dest_geo["lon"], 6), "icon": "red"},
        ]

        # Stations have no coordinates, so place each stop marker at the route
        # point a proportional distance along the polyline.
        n = len(fuel_stops)
        last = len(route_coords) - 1
        for s in fuel_stops:
            idx = min(int(s["stop_number"] / (n + 1) * last), last)
            lon, lat = route_coords[idx]
            markers.append({
                "type": "fuel_stop",
                "label": f"Stop {s['stop_number']}",
                "name": s["station_name"],
                "city": s["city"],
                "state": s["state"],
                "price_per_gallon": s["price_per_gallon"],
                "cost_at_stop": s["cost_at_stop"],
                "miles_from_start": s["miles_from_start"],
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "icon": "blue",
            })

        all_lats = [m["lat"] for m in markers]
        all_lons = [m["lon"] for m in markers]
        step = max(1, len(route_coords) // 500)

        return {
            "center": {"lat": round((min(all_lats) + max(all_lats)) / 2, 6),
                       "lon": round((min(all_lons) + max(all_lons)) / 2, 6)},
            "markers": markers,
            "route_polyline": route_coords[::step],
            "leaflet_tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "leaflet_attribution": '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }

    def plan(self, origin, destination):
        origin_geo = self.geocode(origin)
        dest_geo = self.geocode(destination)

        route = self.get_osrm_route(
            origin_geo["lat"], origin_geo["lon"],
            dest_geo["lat"], dest_geo["lon"],
        )

        fuel_stops = self.plan_fuel_stops(route["coordinates"], route["distance_miles"])
        cost_summary = self.calculate_total_fuel_cost(route["distance_miles"], fuel_stops)
        map_data = self.build_map_data(origin_geo, dest_geo, route["coordinates"], fuel_stops)

        return {
            "origin": {
                "input": origin,
                "display_name": origin_geo["display_name"],
                "lat": round(origin_geo["lat"], 6),
                "lon": round(origin_geo["lon"], 6),
            },
            "destination": {
                "input": destination,
                "display_name": dest_geo["display_name"],
                "lat": round(dest_geo["lat"], 6),
                "lon": round(dest_geo["lon"], 6),
            },
            "route": {
                "distance_miles": route["distance_miles"],
                "duration_hours": round(route["duration_seconds"] / 3600, 2),
                "duration_formatted": format_duration(route["duration_seconds"]),
                "polyline": {
                    "type": "LineString",
                    "coordinates": route["coordinates"],
                },
            },
            "fuel_stops": fuel_stops,
            "cost_summary": cost_summary,
            "map": map_data,
        }
