"""
Routing service using OpenRouteService Directions API.
Fetches route geometry, distance, duration, and segments.
"""
import requests
from django.conf import settings
from typing import Dict, List, Optional, Tuple


class RoutingService:
    """Service for fetching routes from OpenRouteService."""

    BASE_URL = f"{settings.OPENROUTESERVICE_BASE_URL}/directions"

    @classmethod
    def get_route(
        cls,
        start_coords: Tuple[float, float],
        end_coords: Tuple[float, float],
        via_coords: Optional[List[Tuple[float, float]]] = None
    ) -> Dict:
        """
        Get route from start to end coordinates.

        Args:
            start_coords: Tuple of (latitude, longitude) for start
            end_coords: Tuple of (latitude, longitude) for end
            via_coords: Optional list of via points

        Returns:
            Dict containing:
                - polyline: Encoded polyline string
                - distance_miles: Total distance in miles
                - duration_hours: Total duration in hours
                - segments: List of route segments with geometry and instructions
        """
        if not settings.OPENROUTESERVICE_API_KEY:
            raise ValueError("OpenRouteService API key not configured")

        # OpenRouteService expects coordinates as [lng, lat]
        coordinates = [
            [start_coords[1], start_coords[0]]  # [lng, lat]
        ]

        # Add via points if provided
        if via_coords:
            for via in via_coords:
                coordinates.append([via[1], via[0]])

        # Add end point
        coordinates.append([end_coords[1], end_coords[0]])

        payload = {
            "coordinates": coordinates,
            "format": "json",
            "geometry": True,
            "instructions": True,
            "extra_info": ["waytype", "surface"],
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": settings.OPENROUTESERVICE_API_KEY,
        }

        print(headers)

        print(payload)

        print(f"{cls.BASE_URL}/driving-car")
        try:
            response = requests.post(
                f"{cls.BASE_URL}/driving-car",
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()

            if not data.get("routes") or len(data["routes"]) == 0:
                raise Exception("No route found")

            route = data["routes"][0]
            summary = route["summary"]

            # Convert distance from meters to miles
            distance_meters = summary["distance"]
            distance_miles = distance_meters / 1609.34

            # Convert duration from seconds to hours
            duration_seconds = summary["duration"]
            duration_hours = duration_seconds / 3600

            # Extract polyline (OpenRouteService returns encoded polyline string when format=json)
            polyline = route.get("geometry", "")

            # Extract all steps first (before splitting segments)
            all_steps = []
            if "segments" in route and len(route["segments"]) > 0:
                for segment in route["segments"]:
                    if "steps" in segment:
                        for step in segment["steps"]:
                            all_steps.append({
                                "distance_miles": step["distance"] / 1609.34,
                                "duration_hours": step["duration"] / 3600,
                                "instruction": step.get("instruction", ""),
                                "way_points": step.get("way_points", []),
                            })

            # Extract segments
            segments = []
            if "segments" in route and len(route["segments"]) > 1:
                # Multiple segments from OpenRouteService - use them as-is with their steps
                for segment in route["segments"]:
                    segment_data = {
                        "distance_miles": segment["distance"] / 1609.34,
                        "duration_hours": segment["duration"] / 3600,
                        "steps": []
                    }

                    if "steps" in segment:
                        for step in segment["steps"]:
                            step_data = {
                                "distance_miles": step["distance"] / 1609.34,
                                "duration_hours": step["duration"] / 3600,
                                "instruction": step.get("instruction", ""),
                                "way_points": step.get("way_points", []),
                            }
                            segment_data["steps"].append(step_data)

                    segments.append(segment_data)

            # If no segments or only 1 segment, split route into smaller segments for better fuel stop detection
            # But preserve the steps we extracted
            if not segments or len(segments) == 1:
                # Split the route into smaller segments (every 200 miles) for better HOS compliance tracking
                segment_size_miles = 200.0
                num_segments = max(1, int(distance_miles / segment_size_miles) + (1 if distance_miles % segment_size_miles > 0 else 0))

                if num_segments == 1:
                    # If route is less than 200 miles, use single segment with all steps
                    segments = [{
                        "distance_miles": distance_miles,
                        "duration_hours": duration_hours,
                        "steps": all_steps  # Preserve all steps
                    }]
                else:
                    # Split into multiple segments and distribute steps proportionally
                    segment_distance = distance_miles / num_segments
                    segment_duration = duration_hours / num_segments

                    segments = []
                    if all_steps:
                        steps_per_segment = len(all_steps) / num_segments
                        for i in range(num_segments):
                            start_idx = int(i * steps_per_segment)
                            end_idx = int((i + 1) * steps_per_segment) if i < num_segments - 1 else len(all_steps)
                            segment_steps = all_steps[start_idx:end_idx]

                            segments.append({
                                "distance_miles": segment_distance,
                                "duration_hours": segment_duration,
                                "steps": segment_steps  # Include steps for this segment
                            })
                    else:
                        # No steps available, create segments without steps
                        for i in range(num_segments):
                            segments.append({
                                "distance_miles": segment_distance,
                                "duration_hours": segment_duration,
                                "steps": []
                            })

            return {
                "polyline": polyline,
                "distance_miles": distance_miles,
                "duration_hours": duration_hours,
                "segments": segments,
            }

        except requests.RequestException as e:
            raise Exception(f"Routing failed: {str(e)}")

