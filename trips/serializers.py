"""
Serializers for Trip API endpoints.
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer, extend_schema_field
from .models import Trip, Route, TimelineEvent, DailyLog, Stop


@extend_schema_serializer(
    examples=[
        {
            "current_location": {"lat": 40.7128, "lng": -74.0060},
            "pickup_location": {"lat": 40.7580, "lng": -73.9855},
            "dropoff_location": {"lat": 34.0522, "lng": -118.2437},
            "current_cycle_used_hours": 0.0,
        }
    ]
)
class TripInputSerializer(serializers.Serializer):
    """Serializer for trip planning input."""

    current_location = serializers.DictField(
        help_text="Current location as {'lat': float, 'lng': float} or address string"
    )
    pickup_location = serializers.DictField(
        help_text="Pickup location as {'lat': float, 'lng': float} or address string"
    )
    dropoff_location = serializers.DictField(
        help_text="Dropoff location as {'lat': float, 'lng': float} or address string"
    )
    current_cycle_used_hours = serializers.FloatField(
        min_value=0.0,
        max_value=70.0,
        help_text="Hours already used in current 70-hour cycle"
    )


class RouteSerializer(serializers.ModelSerializer):
    """Serializer for route data."""

    class Meta:
        model = Route
        fields = ["polyline", "distance_miles", "duration_hours", "segments"]

    def to_representation(self, instance):
        """Convert to API response format."""
        return {
            "polyline": instance.polyline,
            "distanceMiles": round(instance.distance_miles, 2),
            "durationHours": round(instance.duration_hours, 2),
            "segments": instance.segments,
        }


class DailyLogSegmentSerializer(serializers.Serializer):
    """Serializer for daily log segments."""

    startTime = serializers.DateTimeField()
    endTime = serializers.DateTimeField()
    startIndex = serializers.IntegerField()
    endIndex = serializers.IntegerField()
    rowIndex = serializers.IntegerField()
    status = serializers.CharField()
    location = serializers.CharField()
    remarks = serializers.CharField()


class DailyLogSerializer(serializers.ModelSerializer):
    """Serializer for daily log sheets."""

    segments = DailyLogSegmentSerializer(many=True, read_only=True)

    class Meta:
        model = DailyLog
        fields = ["date", "segments", "driving_hours", "on_duty_hours"]

    def to_representation(self, instance):
        """Convert to API response format."""
        from datetime import datetime

        segments_data = []
        for seg in instance.segments:
            start_time = seg.get("start_time")
            end_time = seg.get("end_time")

            # Handle datetime serialization
            if isinstance(start_time, datetime):
                start_time_str = start_time.isoformat()
            elif isinstance(start_time, str):
                start_time_str = start_time
            else:
                start_time_str = str(start_time)

            if isinstance(end_time, datetime):
                end_time_str = end_time.isoformat()
            elif isinstance(end_time, str):
                end_time_str = end_time
            else:
                end_time_str = str(end_time)

            segments_data.append({
                "startTime": start_time_str,
                "endTime": end_time_str,
                "startIndex": seg.get("startIndex", 0),
                "endIndex": seg.get("endIndex", 0),
                "rowIndex": seg.get("rowIndex", 0),
                "status": seg.get("status", ""),
                "location": seg.get("location", ""),
                "remarks": seg.get("remarks", ""),
            })

        return {
            "date": instance.date.isoformat(),
            "segments": segments_data,
            "totals": {
                "drivingHours": round(instance.driving_hours, 2),
                "onDutyHours": round(instance.on_duty_hours, 2),
            },
        }


class StopSerializer(serializers.ModelSerializer):
    """Serializer for stops."""

    class Meta:
        model = Stop
        fields = ["stop_type", "time", "location", "remarks"]

    def to_representation(self, instance):
        """Convert to API response format."""
        return {
            "type": instance.stop_type,
            "time": instance.time.isoformat(),
            "location": instance.location,
            "remarks": instance.remarks,
        }


class TripResponseSerializer(serializers.ModelSerializer):
    """Serializer for complete trip response."""

    route = RouteSerializer(read_only=True)
    logs = DailyLogSerializer(many=True, read_only=True, source="daily_logs")
    stops = StopSerializer(many=True, read_only=True)

    class Meta:
        model = Trip
        fields = ["id", "route", "logs", "stops"]

    def to_representation(self, instance):
        """Convert to API response format."""
        # Get route
        route_data = {}
        if hasattr(instance, "route"):
            route_serializer = RouteSerializer(instance.route)
            route_data = route_serializer.data

        # Get daily logs
        daily_logs = instance.daily_logs.all().order_by("date")
        logs_serializer = DailyLogSerializer(daily_logs, many=True)
        logs_data = logs_serializer.data

        # Get stops
        stops = instance.stops.all().order_by("time")
        stops_serializer = StopSerializer(stops, many=True)
        stops_data = stops_serializer.data

        # Calculate meta
        total_days = len(logs_data)
        total_distance = route_data.get("distanceMiles", 0.0) if route_data else 0.0

        return {
            "tripId": instance.id,
            "route": route_data,
            "logs": logs_data,
            "stops": stops_data,
            "meta": {
                "totalDays": total_days,
                "totalDistanceMiles": round(total_distance, 2),
            },
        }

