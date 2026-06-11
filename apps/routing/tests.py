from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.routing.models import FuelStation
from apps.routing.services import RoutePlanner
from apps.routing.utils import format_duration, states_in_bbox


class UtilsTests(SimpleTestCase):
    def test_format_duration(self):
        self.assertEqual(format_duration(0), "0m")
        self.assertEqual(format_duration(600), "10m")
        self.assertEqual(format_duration(3660), "1h 1m")

    def test_states_in_bbox_california(self):
        coords = [[-122.4, 37.8], [-118.2, 34.0]]  # SF -> LA
        states = states_in_bbox(coords)
        self.assertIn("CA", states)
        self.assertNotIn("ME", states)

    def test_states_in_bbox_chicago_houston(self):
        coords = [[-87.6, 41.8], [-95.4, 29.8]]
        states = states_in_bbox(coords)
        self.assertIn("IL", states)
        self.assertIn("TX", states)


class PlannerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("init_constants")
        FuelStation.objects.bulk_create([
            FuelStation(opis_id=1, name="A", address="x", city="Dallas", state="TX", rack_id=1, retail_price=Decimal("3.00")),
            FuelStation(opis_id=2, name="B", address="x", city="Austin", state="TX", rack_id=1, retail_price=Decimal("2.50")),
            FuelStation(opis_id=3, name="C", address="x", city="Houston", state="TX", rack_id=1, retail_price=Decimal("4.00")),
        ])

    def setUp(self):
        # A short route whose bounding box sits inside Texas
        self.coords = [[-99.0, 31.0], [-97.0, 33.0], [-95.0, 31.0]]
        self.planner = RoutePlanner()

    def test_no_stops_when_within_one_tank(self):
        self.assertEqual(self.planner.plan_fuel_stops(self.coords, 400), [])

    def test_picks_cheapest_stations_in_order(self):
        stops = self.planner.plan_fuel_stops(self.coords, 1200)  # ceil(1200/500) - 1 = 2 stops
        self.assertEqual(len(stops), 2)
        self.assertEqual(stops[0]["price_per_gallon"], 2.50)
        self.assertEqual(stops[1]["price_per_gallon"], 3.00)
        self.assertLess(stops[0]["miles_from_start"], stops[1]["miles_from_start"])

    def test_cost_summary(self):
        stops = self.planner.plan_fuel_stops(self.coords, 1200)
        summary = self.planner.calculate_total_fuel_cost(1200, stops)
        self.assertEqual(summary["vehicle_range_miles"], 500)
        self.assertEqual(summary["miles_per_gallon"], 10.0)
        self.assertGreater(summary["estimated_total_fuel_cost_usd"], 0)

    def test_map_data_has_all_markers(self):
        stops = self.planner.plan_fuel_stops(self.coords, 1200)
        origin = {"lat": 31.0, "lon": -99.0, "display_name": "Start, TX"}
        dest = {"lat": 31.0, "lon": -95.0, "display_name": "End, TX"}
        data = self.planner.build_map_data(origin, dest, self.coords, stops)
        types = [m["type"] for m in data["markers"]]
        self.assertIn("origin", types)
        self.assertIn("destination", types)
        self.assertEqual(types.count("fuel_stop"), 2)


class RouteViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("init_constants")

    def setUp(self):
        self.client = APIClient()

    def test_get_returns_schema(self):
        res = self.client.get("/api/route/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["endpoint"], "/api/route/")

    def test_post_missing_fields(self):
        res = self.client.post("/api/route/", {}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_post_same_origin_and_destination(self):
        res = self.client.post(
            "/api/route/",
            {"origin": "Dallas, TX", "destination": "Dallas, TX"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    @patch("apps.routing.views.RoutePlanner")
    def test_post_valid_route(self, mock_planner):
        mock_planner.return_value.plan.return_value = {"ok": True}
        res = self.client.post(
            "/api/route/",
            {"origin": "Chicago, IL", "destination": "Houston, TX"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, {"ok": True})
