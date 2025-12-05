"""
Geocoding service using OpenRouteService API.
Converts addresses to coordinates and vice versa.
"""
import requests
from django.conf import settings
from typing import Dict, Tuple, Optional


class GeocodingService:
    """Service for geocoding addresses and coordinates."""

    BASE_URL = f"{settings.OPENROUTESERVICE_BASE_URL}/geocoding"

    @classmethod
    def geocode_address(cls, address: str) -> Optional[Tuple[float, float]]:
        """
        Geocode an address string to lat/lng coordinates.

        Args:
            address: Address string to geocode

        Returns:
            Tuple of (latitude, longitude) or None if geocoding fails
        """
        if not settings.OPENROUTESERVICE_API_KEY:
            raise ValueError("OpenRouteService API key not configured")

        params = {
            "text": address,
            "size": 1,
        }

        headers = {
            "Authorization": settings.OPENROUTESERVICE_API_KEY,
        }

        try:
            response = requests.get(
                f"{cls.BASE_URL}/search",
                params=params,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            if data.get("features") and len(data["features"]) > 0:
                coordinates = data["features"][0]["geometry"]["coordinates"]
                # OpenRouteService returns [lng, lat], convert to [lat, lng]
                return (coordinates[1], coordinates[0])

            return None

        except requests.RequestException as e:
            raise Exception(f"Geocoding failed: {str(e)}")

    @classmethod
    def parse_location(cls, location) -> Tuple[float, float]:
        """
        Parse a location input that can be either:
        - A string address (will be geocoded)
        - A dict with 'lat' and 'lng' keys
        - A dict with 'latitude' and 'longitude' keys

        Args:
            location: Location input (string or dict)

        Returns:
            Tuple of (latitude, longitude)
        """
        if isinstance(location, str):
            # Geocode the address
            coords = cls.geocode_address(location)
            if coords is None:
                raise ValueError(f"Could not geocode address: {location}")
            return coords

        elif isinstance(location, dict):
            # Extract coordinates from dict
            if "lat" in location and "lng" in location:
                return (float(location["lat"]), float(location["lng"]))
            elif "latitude" in location and "longitude" in location:
                return (float(location["latitude"]), float(location["longitude"]))
            else:
                raise ValueError("Location dict must contain 'lat'/'lng' or 'latitude'/'longitude'")

        else:
            raise ValueError("Location must be a string address or dict with coordinates")

