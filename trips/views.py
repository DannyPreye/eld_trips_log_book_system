"""
API views for Trip planning and management.
"""
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from datetime import datetime
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from .models import Trip, Route, TimelineEvent, DailyLog, Stop
from .serializers import TripInputSerializer, TripResponseSerializer
from .services.geocoding import GeocodingService
from .services.routing import RoutingService
from .services.hos_engine import HOSEngine
from .services.log_slicer import DailyLogSlicer
from .services.grid_mapper import GridMapper


class TripPlanView(APIView):
    """Main endpoint for trip planning."""

    @extend_schema(
        request=TripInputSerializer,
        responses={
            201: TripResponseSerializer,
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Validation error",
                examples=[
                    OpenApiExample(
                        "Validation Error",
                        value={
                            "current_location": ["This field is required."],
                            "pickup_location": ["This field is required."],
                        }
                    )
                ]
            ),
            500: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Server error",
                examples=[
                    OpenApiExample(
                        "Server Error",
                        value={"error": "Routing failed: API key not configured"}
                    )
                ]
            ),
        },
        examples=[
            OpenApiExample(
                "Trip Planning Request",
                value={
                    "current_location": {"lat": 40.7128, "lng": -74.0060},
                    "pickup_location": {"lat": 40.7580, "lng": -73.9855},
                    "dropoff_location": {"lat": 34.0522, "lng": -118.2437},
                    "current_cycle_used_hours": 0.0,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Trip Planning Response",
                value={
                    "tripId": 1,
                    "route": {
                        "polyline": "encoded_polyline_string",
                        "distanceMiles": 1430.2,
                        "durationHours": 27.5,
                        "segments": []
                    },
                    "logs": [
                        {
                            "date": "2025-10-14",
                            "segments": [
                                {
                                    "startTime": "2025-10-14T06:00:00Z",
                                    "endTime": "2025-10-14T10:30:00Z",
                                    "startIndex": 24,
                                    "endIndex": 42,
                                    "rowIndex": 2,
                                    "status": "DRIVING",
                                    "location": "Route Segment",
                                    "remarks": "Route segment"
                                }
                            ],
                            "totals": {
                                "drivingHours": 6.5,
                                "onDutyHours": 7.75
                            }
                        }
                    ],
                    "stops": [
                        {
                            "type": "BREAK",
                            "time": "2025-10-14T10:30:00Z",
                            "location": "Rest Stop",
                            "remarks": "30-minute break"
                        }
                    ],
                    "meta": {
                        "totalDays": 3,
                        "totalDistanceMiles": 1430.2
                    }
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        """
        POST /api/trip/plan

        Process trip input:
        1. Validate input
        2. Geocode locations
        3. Fetch route from OpenRouteService
        4. Run HOS engine
        5. Slice into daily logs
        6. Map grid indices
        7. Save to database
        8. Return structured response
        """
        # Validate input
        serializer = TripInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            # Parse locations
            geocoding_service = GeocodingService()

            current_coords = geocoding_service.parse_location(data["current_location"])
            pickup_coords = geocoding_service.parse_location(data["pickup_location"])
            dropoff_coords = geocoding_service.parse_location(data["dropoff_location"])

            # Create trip record
            trip = Trip.objects.create(
                current_location_lat=current_coords[0],
                current_location_lng=current_coords[1],
                pickup_location_lat=pickup_coords[0],
                pickup_location_lng=pickup_coords[1],
                dropoff_location_lat=dropoff_coords[0],
                dropoff_location_lng=dropoff_coords[1],
                current_cycle_used_hours=data["current_cycle_used_hours"],
                status="processing"
            )

            # Get route from OpenRouteService
            routing_service = RoutingService()
            route_data = routing_service.get_route(
                start_coords=pickup_coords,
                end_coords=dropoff_coords
            )

            # Save route
            route = Route.objects.create(
                trip=trip,
                polyline=route_data["polyline"],
                distance_miles=route_data["distance_miles"],
                duration_hours=route_data["duration_hours"],
                segments=route_data["segments"]
            )

            # Prepare route segments for HOS engine
            route_segments = []
            for seg in route_data["segments"]:
                route_segments.append({
                    "distance_miles": seg.get("distance_miles", 0),
                    "duration_hours": seg.get("duration_hours", 0),
                    "location": "Route Segment",
                    "remarks": f"Route segment"
                })

            # Run HOS compliance engine
            start_time = timezone.now()
            timeline, stops_data = HOSEngine.process_trip(
                route_segments=route_segments,
                start_time=start_time,
                current_cycle_hours=data["current_cycle_used_hours"],
                pickup_location="Pickup Location",
                dropoff_location="Dropoff Location",
                pickup_coords=pickup_coords,
                dropoff_coords=dropoff_coords,
                route_polyline=route_data["polyline"],
                total_route_distance_miles=route_data["distance_miles"]
            )

            # Save timeline events
            for event_data in timeline:
                TimelineEvent.objects.create(
                    trip=trip,
                    start_time=event_data["start_time"],
                    end_time=event_data["end_time"],
                    status=event_data["status"],
                    location=event_data.get("location", ""),
                    remarks=event_data.get("remarks", "")
                )

            # Save stops
            for stop_data in stops_data:
                Stop.objects.create(
                    trip=trip,
                    stop_type=stop_data["type"],
                    time=stop_data["time"],
                    location=stop_data.get("location", ""),
                    latitude=stop_data.get("latitude"),
                    longitude=stop_data.get("longitude"),
                    remarks=stop_data.get("remarks", "")
                )

            # Slice into daily logs
            daily_logs_data = DailyLogSlicer.slice_timeline(timeline)

            # Map grid indices
            daily_logs_data = GridMapper.map_all_logs(daily_logs_data)

            # Save daily logs
            for log_data in daily_logs_data:
                # Convert datetime objects in segments to ISO strings for JSONField
                serialized_segments = []
                for seg in log_data["segments"]:
                    serialized_seg = seg.copy()
                    if isinstance(seg.get("start_time"), datetime):
                        serialized_seg["start_time"] = seg["start_time"].isoformat()
                    if isinstance(seg.get("end_time"), datetime):
                        serialized_seg["end_time"] = seg["end_time"].isoformat()
                    serialized_segments.append(serialized_seg)

                DailyLog.objects.create(
                    trip=trip,
                    date=log_data["date"],
                    driving_hours=log_data["driving_hours"],
                    on_duty_hours=log_data["on_duty_hours"],
                    segments=serialized_segments
                )

            # Update trip status
            trip.status = "completed"
            trip.save()

            # Return response
            response_serializer = TripResponseSerializer(trip)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            # Update trip status if it exists
            if 'trip' in locals():
                trip.status = "failed"
                trip.save()

            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TripDetailView(APIView):
    """Get trip details."""

    @extend_schema(
        responses={
            200: TripResponseSerializer,
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Trip not found",
                examples=[
                    OpenApiExample(
                        "Not Found",
                        value={"error": "Trip not found"}
                    )
                ]
            ),
        },
    )
    def get(self, request, trip_id):
        """
        GET /api/trip/{id}

        Fetch complete trip details.
        """
        try:
            trip = Trip.objects.get(id=trip_id)
            serializer = TripResponseSerializer(trip)
            return Response(serializer.data)
        except Trip.DoesNotExist:
            return Response(
                {"error": "Trip not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class TripLogsView(APIView):
    """Get trip logs for rendering."""

    @extend_schema(
        responses={
            200: TripResponseSerializer,
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Trip not found",
                examples=[
                    OpenApiExample(
                        "Not Found",
                        value={"error": "Trip not found"}
                    )
                ]
            ),
        },
    )
    def get(self, request, trip_id):
        """
        GET /api/trip/{id}/logs

        Returns structured logs for frontend rendering.
        """
        try:
            trip = Trip.objects.get(id=trip_id)
            serializer = TripResponseSerializer(trip)
            return Response(serializer.data)
        except Trip.DoesNotExist:
            return Response(
                {"error": "Trip not found"},
                status=status.HTTP_404_NOT_FOUND
            )


@extend_schema(
    operation_id="health_check",
    summary="Health Check",
    description="Basic health check endpoint",
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Service health status",
            examples=[
                OpenApiExample(
                    "Healthy",
                    value={
                        "status": "healthy",
                        "service": "ELD Trip Planner Backend"
                    }
                )
            ]
        ),
    },
)
@api_view(["GET"])
def health_check(request):
    """
    GET /api/healthcheck

    Basic health check endpoint.
    """
    return Response({
        "status": "healthy",
        "service": "ELD Trip Planner Backend"
    })
