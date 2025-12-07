"""
Utilities for working with encoded polylines.
Used to calculate coordinates along a route for stop locations.
"""
import math


def decode_polyline(polyline: str) -> list:
    """
    Decode an encoded polyline string into a list of [lat, lng] coordinates.

    Args:
        polyline: Encoded polyline string from OpenRouteService

    Returns:
        List of [lat, lng] coordinate pairs
    """
    if not polyline:
        return []

    coordinates = []
    index = 0
    lat = 0
    lng = 0

    while index < len(polyline):
        # Decode latitude
        shift = 0
        result = 0
        while True:
            byte = ord(polyline[index]) - 63
            index += 1
            result |= (byte & 0x1f) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += delta_lat

        # Decode longitude
        shift = 0
        result = 0
        while True:
            byte = ord(polyline[index]) - 63
            index += 1
            result |= (byte & 0x1f) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += delta_lng

        coordinates.append([lat / 1e5, lng / 1e5])

    return coordinates


def calculate_distance_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate distance between two coordinates using Haversine formula.

    Args:
        lat1, lng1: First coordinate
        lat2, lng2: Second coordinate

    Returns:
        Distance in miles
    """
    R = 3959  # Earth's radius in miles

    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def get_coordinate_at_distance(polyline: str, target_distance_miles: float, total_distance_miles: float) -> tuple:
    """
    Get the coordinate at a specific distance along the route.

    Args:
        polyline: Encoded polyline string
        target_distance_miles: Distance along route to find coordinate
        total_distance_miles: Total distance of the route

    Returns:
        Tuple of (latitude, longitude) or None if not found
    """
    if not polyline or target_distance_miles <= 0:
        return None

    coordinates = decode_polyline(polyline)
    if len(coordinates) < 2:
        return None

    # If target distance is beyond route, return last coordinate
    if target_distance_miles >= total_distance_miles:
        return (coordinates[-1][0], coordinates[-1][1])

    # Calculate cumulative distance and find the segment containing target distance
    cumulative_distance = 0.0

    for i in range(len(coordinates) - 1):
        segment_distance = calculate_distance_miles(
            coordinates[i][0], coordinates[i][1],
            coordinates[i + 1][0], coordinates[i + 1][1]
        )

        if cumulative_distance + segment_distance >= target_distance_miles:
            # Target is in this segment
            # Interpolate between the two points
            ratio = (target_distance_miles - cumulative_distance) / segment_distance if segment_distance > 0 else 0

            lat = coordinates[i][0] + (coordinates[i + 1][0] - coordinates[i][0]) * ratio
            lng = coordinates[i][1] + (coordinates[i + 1][1] - coordinates[i][1]) * ratio

            return (lat, lng)

        cumulative_distance += segment_distance

    # Fallback to last coordinate
    return (coordinates[-1][0], coordinates[-1][1])

