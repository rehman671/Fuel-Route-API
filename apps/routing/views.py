from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import RoutePlanner


class RouteView(APIView):
    """
    POST /api/route/
    Plan a fuel-optimal driving route between two US locations.
    """

    def post(self, request):
        origin = request.data.get("origin", "").strip()
        destination = request.data.get("destination", "").strip()

        if not origin or not destination:
            return Response(
                {
                    "error": "Both 'origin' and 'destination' are required.",
                    "example": {
                        "origin": "Los Angeles, CA",
                        "destination": "New York, NY",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if origin.lower() == destination.lower():
            return Response(
                {"error": "Origin and destination must be different locations."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = RoutePlanner().plan(origin, destination)
            return Response(result, status=status.HTTP_200_OK)

        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception as exc:
            return Response(
                {"error": "An unexpected error occurred.", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request):
        """Return API documentation."""
        return Response(
            {
                "endpoint": "/api/route/",
                "method": "POST",
                "description": (
                    "Plan a fuel-optimal driving route between two US locations. "
                    "Returns the route map data, optimal fuel stops based on lowest "
                    "price along the route, and total estimated fuel cost."
                ),
                "vehicle_assumptions": {
                    "max_range_miles": 500,
                    "miles_per_gallon": 10,
                    "tank_size_gallons": 50,
                },
                "request_body": {
                    "origin": "string — starting location (city, state or full address)",
                    "destination": "string — ending location (city, state or full address)",
                },
                "response_schema": {
                    "origin": "Geocoded origin with lat/lon",
                    "destination": "Geocoded destination with lat/lon",
                    "route": {
                        "distance_miles": "Total driving distance",
                        "duration_formatted": "Estimated drive time",
                        "polyline": "GeoJSON LineString of the full route",
                    },
                    "fuel_stops": [
                        {
                            "stop_number": "integer",
                            "station_name": "string",
                            "address": "string",
                            "city": "string",
                            "state": "string",
                            "price_per_gallon": "float (USD)",
                            "miles_from_start": "float",
                            "gallons_to_fill": "float",
                            "cost_at_stop": "float (USD)",
                        }
                    ],
                    "cost_summary": {
                        "total_distance_miles": "float",
                        "total_gallons_needed": "float",
                        "miles_per_gallon": 10,
                        "vehicle_range_miles": 500,
                        "estimated_total_fuel_cost_usd": "float",
                    },
                    "map": {
                        "center": "{'lat': float, 'lon': float}",
                        "markers": "List of map pins (origin, destination, fuel stops)",
                        "route_polyline": "Downsampled [lon, lat] pairs for display",
                        "leaflet_tile_url": "OpenStreetMap tile URL for Leaflet.js",
                        "leaflet_attribution": "Required OSM attribution string",
                    },
                },
                "example_request": {
                    "origin": "Chicago, IL",
                    "destination": "Houston, TX",
                },
            }
        )
