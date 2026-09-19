import json
import logging
import urllib.parse
import urllib.request
from django.conf import settings

logger = logging.getLogger(__name__)

ORS_BASE_URL = "https://api.heigit.org/openrouteservice/v2"


def get_ors_headers():
    """
    Returns headers with the OpenRouteService API Key from Django settings.
    Key is loaded securely from environment variable OPENROUTESERVICE_API_KEY.
    """
    api_key = getattr(settings, 'OPENROUTESERVICE_API_KEY', '').strip()
    headers = {
        "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = api_key
    return headers


def get_ors_directions(coordinates, profile="driving-car"):
    """
    Calls OpenRouteService v2 Directions API with coordinates array.
    Supports 2 or more coordinates (e.g. [ [lng1, lat1], [lng2, lat2], ... ])
    Returns dict with geometry (GeoJSON list of [lng, lat]), distance_km, duration_mins.
    """
    if not coordinates or len(coordinates) < 2:
        raise ValueError("At least 2 coordinate pairs are required for routing.")

    url = f"{ORS_BASE_URL}/directions/{profile}/geojson"
    headers = get_ors_headers()

    body_data = json.dumps({"coordinates": coordinates}).encode("utf-8")

    req = urllib.request.Request(url, data=body_data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status == 200:
                res_data = json.loads(response.read().decode("utf-8"))
                features = res_data.get("features", [])
                if not features:
                    raise ValueError("No route found between selected locations.")

                feature = features[0]
                geometry = feature.get("geometry", {}).get("coordinates", [])
                summary = feature.get("properties", {}).get("summary", {})

                distance_m = summary.get("distance", 0.0)
                duration_s = summary.get("duration", 0.0)

                distance_km = round(distance_m / 1000.0, 1)
                duration_mins = round(duration_s / 60.0)

                return {
                    "success": True,
                    "geometry": geometry,  # [[lng, lat], [lng, lat], ...]
                    "distance_km": distance_km,
                    "duration_mins": duration_mins,
                    "raw": res_data,
                }
            else:
                logger.error(f"ORS API status error {response.status}")
                raise ValueError(f"OpenRouteService returned status code {response.status}")
    except Exception as e:
        logger.error(f"Error fetching ORS route: {e}")
        # Fallback to direct straight line GeoJSON if ORS fails or network error occurs
        fallback_distance = calculate_haversine_distance(coordinates[0], coordinates[-1])
        return {
            "success": False,
            "error": str(e),
            "geometry": coordinates,
            "distance_km": round(fallback_distance, 1),
            "duration_mins": round((fallback_distance / 60.0) * 60),
        }


def geocode_location(query):
    """
    Geocodes a search string into [lat, lng, display_name].
    Uses ORS Geocoding API if key available, with fallback to Nominatim (India scoped).
    """
    if not query or not query.strip():
        return []

    clean_query = query.strip()
    api_key = getattr(settings, 'OPENROUTESERVICE_API_KEY', '').strip()

    # Try ORS Geocode first
    if api_key:
        try:
            params = urllib.parse.urlencode({"api_key": api_key, "text": clean_query, "size": 6})
            url = f"{ORS_BASE_URL}/geocode/search?{params}"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=6) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    features = data.get("features", [])
                    results = []
                    for feat in features:
                        coords = feat.get("geometry", {}).get("coordinates", [0, 0])
                        props = feat.get("properties", {})
                        results.append({
                            "display_name": props.get("label", clean_query),
                            "short_name": props.get("name", props.get("label", clean_query)),
                            "lat": coords[1],
                            "lng": coords[0],
                        })
                    if results:
                        return results
        except Exception as e:
            logger.warning(f"ORS Geocode failed: {e}. Falling back to Nominatim.")

    # Fallback to Nominatim OSM (India scoped)
    try:
        params = urllib.parse.urlencode({
            "format": "json",
            "q": clean_query,
            "countrycodes": "in",
            "addressdetails": 1,
            "limit": 8
        })
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "Kaapool-Carpool-App/1.0"})
        with urllib.request.urlopen(req, timeout=6) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                results = []
                for place in data:
                    full_name = place.get("display_name", "")
                    short_parts = full_name.split(",")[:3]
                    results.append({
                        "display_name": full_name,
                        "short_name": ", ".join(short_parts).strip(),
                        "lat": float(place.get("lat")),
                        "lng": float(place.get("lon")),
                    })
                return results
    except Exception as e:
        logger.error(f"Nominatim Geocode failed: {e}")

    return []


def reverse_geocode_location(lat, lng):
    """
    Reverse geocodes lat/lng coordinates to a human-readable address.
    """
    try:
        params = urllib.parse.urlencode({
            "format": "json",
            "lat": lat,
            "lon": lng,
        })
        url = f"https://nominatim.openstreetmap.org/reverse?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "Kaapool-Carpool-App/1.0"})
        with urllib.request.urlopen(req, timeout=6) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                full_name = data.get("display_name", f"{lat:.4f}, {lng:.4f}")
                short_parts = full_name.split(",")[:3]
                return {
                    "full_address": full_name,
                    "short_address": ", ".join(short_parts).strip(),
                    "lat": float(lat),
                    "lng": float(lng),
                }
    except Exception as e:
        logger.error(f"Reverse geocode failed: {e}")

    return {
        "full_address": f"Location ({lat:.4f}, {lng:.4f})",
        "short_address": f"{lat:.4f}, {lng:.4f}",
        "lat": float(lat),
        "lng": float(lng),
    }


def calculate_haversine_distance(coord1, coord2):
    """
    Calculates straight-line distance in km between two [lng, lat] coordinates.
    """
    import math
    lng1, lat1 = coord1
    lng2, lat2 = coord2
    R = 6371.0  # Earth radius in km

    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c
