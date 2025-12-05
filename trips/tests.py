"""
Tests for trips app.
"""
from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock

from .models import Trip, Route, TimelineEvent, DailyLog, Stop
from .services.hos_engine import HOSEngine
from .services.log_slicer import DailyLogSlicer
from .services.grid_mapper import GridMapper
from .services.routing import RoutingService
from .services.geocoding import GeocodingService


class HOSEngineTests(TestCase):
    """Tests for HOS compliance engine."""

    def setUp(self):
        self.start_time = timezone.now()

    def test_11_hour_driving_limit(self):
        """Test that 11-hour driving limit is enforced."""
        # Create segments that exceed 11 hours
        segments = [
            {"distance_miles": 600, "duration_hours": 10},
            {"distance_miles": 100, "duration_hours": 2},  # This should trigger break
        ]

        timeline, stops = HOSEngine.process_trip(
            route_segments=segments,
            start_time=self.start_time,
            current_cycle_hours=0.0
        )

        # Find the break event
        break_events = [e for e in timeline if e["status"] == "SLEEPER"]
        self.assertGreater(len(break_events), 0, "Should have break event")

        # Check break duration is 10 hours
        break_event = break_events[0]
        break_duration = (break_event["end_time"] - break_event["start_time"]).total_seconds() / 3600
        self.assertAlmostEqual(break_duration, 10.0, places=1)

    def test_14_hour_workday_limit(self):
        """Test that 14-hour workday limit is enforced."""
        # Create segments that exceed 14 hours on-duty
        segments = [
            {"distance_miles": 700, "duration_hours": 13},  # 1 hour pickup + 13 hours driving = 14 hours
        ]

        timeline, stops = HOSEngine.process_trip(
            route_segments=segments,
            start_time=self.start_time,
            current_cycle_hours=0.0
        )

        # Should have break event
        break_events = [e for e in timeline if e["status"] == "SLEEPER"]
        self.assertGreater(len(break_events), 0, "Should have break event")

    def test_30_minute_break_requirement(self):
        """Test that 30-minute break is required after 8 hours driving."""
        segments = [
            {"distance_miles": 500, "duration_hours": 8.5},
        ]

        timeline, stops = HOSEngine.process_trip(
            route_segments=segments,
            start_time=self.start_time,
            current_cycle_hours=0.0
        )

        # Find break stops
        break_stops = [s for s in stops if s["type"] == "BREAK"]
        self.assertGreater(len(break_stops), 0, "Should have 30-minute break")

    def test_fuel_stop_insertion(self):
        """Test that fuel stops are inserted every 1000 miles."""
        segments = [
            {"distance_miles": 1200, "duration_hours": 20},
        ]

        timeline, stops = HOSEngine.process_trip(
            route_segments=segments,
            start_time=self.start_time,
            current_cycle_hours=0.0
        )

        # Should have fuel stop
        fuel_stops = [s for s in stops if s["type"] == "FUEL"]
        self.assertGreater(len(fuel_stops), 0, "Should have fuel stop")

    def test_pickup_and_dropoff_added(self):
        """Test that pickup and dropoff events are added."""
        segments = [
            {"distance_miles": 100, "duration_hours": 2},
        ]

        timeline, stops = HOSEngine.process_trip(
            route_segments=segments,
            start_time=self.start_time,
            current_cycle_hours=0.0
        )

        # Check for pickup and dropoff
        pickup_events = [e for e in timeline if "Pickup" in e.get("remarks", "")]
        dropoff_events = [e for e in timeline if "Dropoff" in e.get("remarks", "")]

        self.assertGreater(len(pickup_events), 0, "Should have pickup event")
        self.assertGreater(len(dropoff_events), 0, "Should have dropoff event")


class GridMapperTests(TestCase):
    """Tests for grid index mapper."""

    def test_time_to_index(self):
        """Test timestamp to grid index conversion."""
        # 00:00 should be index 0
        dt = datetime(2025, 1, 1, 0, 0, 0)
        self.assertEqual(GridMapper.time_to_index(dt), 0)

        # 06:00 should be index 24 (6 * 4)
        dt = datetime(2025, 1, 1, 6, 0, 0)
        self.assertEqual(GridMapper.time_to_index(dt), 24)

        # 08:30 should be index 34 (8 * 4 + 2)
        dt = datetime(2025, 1, 1, 8, 30, 0)
        self.assertEqual(GridMapper.time_to_index(dt), 34)

        # 23:45 should be index 95 (23 * 4 + 3)
        dt = datetime(2025, 1, 1, 23, 45, 0)
        self.assertEqual(GridMapper.time_to_index(dt), 95)

    def test_status_to_row_mapping(self):
        """Test duty status to row index mapping."""
        self.assertEqual(GridMapper.STATUS_TO_ROW["OFF_DUTY"], 0)
        self.assertEqual(GridMapper.STATUS_TO_ROW["SLEEPER"], 1)
        self.assertEqual(GridMapper.STATUS_TO_ROW["DRIVING"], 2)
        self.assertEqual(GridMapper.STATUS_TO_ROW["ON_DUTY"], 3)


class DailyLogSlicerTests(TestCase):
    """Tests for daily log slicer."""

    def setUp(self):
        self.start_time = timezone.now()

    def test_single_day_timeline(self):
        """Test slicing a timeline that fits in one day."""
        timeline = [
            {
                "start_time": self.start_time,
                "end_time": self.start_time + timedelta(hours=8),
                "status": "DRIVING",
                "location": "Route",
                "remarks": "Test"
            }
        ]

        daily_logs = DailyLogSlicer.slice_timeline(timeline)

        self.assertEqual(len(daily_logs), 1)
        self.assertEqual(len(daily_logs[0]["segments"]), 1)
        self.assertAlmostEqual(daily_logs[0]["driving_hours"], 8.0, places=1)

    def test_midnight_boundary_slicing(self):
        """Test slicing events that cross midnight."""
        # Create event that crosses midnight
        day_start = datetime.combine(self.start_time.date(), datetime.min.time())
        day_start = timezone.make_aware(day_start)
        midnight = day_start + timedelta(days=1)

        timeline = [
            {
                "start_time": midnight - timedelta(hours=2),
                "end_time": midnight + timedelta(hours=2),
                "status": "DRIVING",
                "location": "Route",
                "remarks": "Crosses midnight"
            }
        ]

        daily_logs = DailyLogSlicer.slice_timeline(timeline)

        # Should be split into two days
        self.assertEqual(len(daily_logs), 2)

        # First day should have 2 hours
        first_day = daily_logs[0]
        self.assertAlmostEqual(first_day["driving_hours"], 2.0, places=1)

        # Second day should have 2 hours
        second_day = daily_logs[1]
        self.assertAlmostEqual(second_day["driving_hours"], 2.0, places=1)

    def test_multi_day_trip(self):
        """Test slicing a multi-day trip."""
        day1_start = datetime.combine(self.start_time.date(), datetime.min.time())
        day1_start = timezone.make_aware(day1_start)

        timeline = [
            {
                "start_time": day1_start + timedelta(hours=8),
                "end_time": day1_start + timedelta(hours=20),
                "status": "DRIVING",
                "location": "Day 1",
                "remarks": "Day 1"
            },
            {
                "start_time": day1_start + timedelta(days=1, hours=6),
                "end_time": day1_start + timedelta(days=1, hours=18),
                "status": "DRIVING",
                "location": "Day 2",
                "remarks": "Day 2"
            }
        ]

        daily_logs = DailyLogSlicer.slice_timeline(timeline)

        self.assertEqual(len(daily_logs), 2)
        self.assertEqual(daily_logs[0]["date"], day1_start.date().isoformat())
        self.assertEqual(daily_logs[1]["date"], (day1_start.date() + timedelta(days=1)).isoformat())


class RoutingServiceTests(TestCase):
    """Tests for routing service."""

    @patch('trips.services.routing.requests.post')
    def test_get_route_success(self, mock_post):
        """Test successful route retrieval."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "routes": [{
                "geometry": "encoded_polyline",
                "summary": {
                    "distance": 160934,  # 100 miles in meters
                    "duration": 7200  # 2 hours in seconds
                },
                "segments": [{
                    "distance": 160934,
                    "duration": 7200,
                    "steps": []
                }]
            }]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        route_data = RoutingService.get_route(
            start_coords=(40.7128, -74.0060),
            end_coords=(40.7580, -73.9855)
        )

        self.assertIn("polyline", route_data)
        self.assertIn("distance_miles", route_data)
        self.assertIn("duration_hours", route_data)
        self.assertAlmostEqual(route_data["distance_miles"], 100.0, places=1)
        self.assertAlmostEqual(route_data["duration_hours"], 2.0, places=1)


class GeocodingServiceTests(TestCase):
    """Tests for geocoding service."""

    @patch('trips.services.geocoding.requests.get')
    def test_geocode_address_success(self, mock_get):
        """Test successful address geocoding."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "features": [{
                "geometry": {
                    "coordinates": [-74.0060, 40.7128]  # [lng, lat]
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        coords = GeocodingService.geocode_address("New York, NY")

        self.assertIsNotNone(coords)
        self.assertEqual(coords[0], 40.7128)  # lat
        self.assertEqual(coords[1], -74.0060)  # lng

    def test_parse_location_dict(self):
        """Test parsing location from dict."""
        location = {"lat": 40.7128, "lng": -74.0060}
        coords = GeocodingService.parse_location(location)

        self.assertEqual(coords[0], 40.7128)
        self.assertEqual(coords[1], -74.0060)

    def test_parse_location_dict_alt_keys(self):
        """Test parsing location from dict with alternative keys."""
        location = {"latitude": 40.7128, "longitude": -74.0060}
        coords = GeocodingService.parse_location(location)

        self.assertEqual(coords[0], 40.7128)
        self.assertEqual(coords[1], -74.0060)


class IntegrationTests(TestCase):
    """Integration tests for full pipeline."""

    @patch('trips.services.routing.RoutingService.get_route')
    @patch('trips.services.geocoding.GeocodingService.parse_location')
    def test_full_trip_processing(self, mock_parse, mock_route):
        """Test full trip processing pipeline."""
        # Mock geocoding
        mock_parse.return_value = (40.7128, -74.0060)

        # Mock routing
        mock_route.return_value = {
            "polyline": "test_polyline",
            "distance_miles": 500.0,
            "duration_hours": 10.0,
            "segments": [
                {
                    "distance_miles": 500.0,
                    "duration_hours": 10.0,
                    "steps": []
                }
            ]
        }

        # Create trip
        trip = Trip.objects.create(
            current_location_lat=40.7128,
            current_location_lng=-74.0060,
            pickup_location_lat=40.7128,
            pickup_location_lng=-74.0060,
            dropoff_location_lat=40.7580,
            dropoff_location_lng=-73.9855,
            current_cycle_used_hours=0.0
        )

        # Process route
        route = Route.objects.create(
            trip=trip,
            polyline="test_polyline",
            distance_miles=500.0,
            duration_hours=10.0,
            segments=mock_route.return_value["segments"]
        )

        # Process HOS
        start_time = timezone.now()
        timeline, stops = HOSEngine.process_trip(
            route_segments=mock_route.return_value["segments"],
            start_time=start_time,
            current_cycle_hours=0.0
        )

        # Slice logs
        daily_logs = DailyLogSlicer.slice_timeline(timeline)

        # Map grid indices
        daily_logs = GridMapper.map_all_logs(daily_logs)

        # Verify results
        self.assertGreater(len(timeline), 0)
        self.assertGreater(len(daily_logs), 0)

        # Check that segments have grid indices
        for log in daily_logs:
            for segment in log["segments"]:
                self.assertIn("startIndex", segment)
                self.assertIn("endIndex", segment)
                self.assertIn("rowIndex", segment)
