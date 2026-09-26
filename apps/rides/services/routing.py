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


def get_ors_directions(coordinates, profile="driving-car", include_alternatives=True):
    """
    Calls OpenRouteService v2 Directions API with coordinates array.
    Supports 2 or more coordinates (e.g. [ [lng1, lat1], [lng2, lat2], ... ])
    Requests genuine alternative routes up to target_count=3 if include_alternatives=True.
    Returns normalized dictionary containing routes array:
    [{ id, distance_km, duration_mins, geometry, label, is_recommended, is_fastest, is_shortest, traffic_segments }, ...]
    """
    if not coordinates or len(coordinates) < 2:
        raise ValueError("At least 2 coordinate pairs are required for routing.")

    url = f"{ORS_BASE_URL}/directions/{profile}/geojson"
    headers = get_ors_headers()

    body_payload = {"coordinates": coordinates}
    if include_alternatives:
        body_payload["alternative_routes"] = {"target_count": 3}

    body_data = json.dumps(body_payload).encode("utf-8")

    req = urllib.request.Request(url, data=body_data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status == 200:
                res_data = json.loads(response.read().decode("utf-8"))
                features = res_data.get("features", [])
                if not features:
                    raise ValueError("No route found between selected locations.")

                # Process all returned genuine route features (up to 4 total)
                raw_routes = []
                for idx, feature in enumerate(features[:4]):
                    geometry = feature.get("geometry", {}).get("coordinates", [])
                    summary = feature.get("properties", {}).get("summary", {})

                    distance_m = summary.get("distance", 0.0)
                    duration_s = summary.get("duration", 0.0)

                    distance_km = round(distance_m / 1000.0, 1)
                    duration_mins = max(1, round(duration_s / 60.0))

                    raw_routes.append({
                        "id": idx,
                        "distance_km": distance_km,
                        "duration_mins": duration_mins,
                        "geometry": geometry,
                        "traffic_segments": [], # Future traffic provider abstraction layer
                    })

                if not raw_routes:
                    raise ValueError("No valid route geometry returned by OpenRouteService.")

                # Identify minimum distance and minimum duration across returned routes
                min_dist = min(r["distance_km"] for r in raw_routes)
                min_dur = min(r["duration_mins"] for r in raw_routes)

                normalized_routes = []
                for r in raw_routes:
                    is_fastest = (r["duration_mins"] == min_dur)
                    is_shortest = (r["distance_km"] == min_dist)
                    is_recommended = (r["id"] == 0)

                    # Dynamic label assignment strictly based on actual calculated values
                    if is_recommended:
                        if is_fastest and is_shortest:
                            label = "Recommended · Fastest & Shortest"
                        elif is_fastest:
                            label = "Recommended · Fastest"
                        elif is_shortest:
                            label = "Recommended · Shortest"
                        else:
                            label = "Recommended"
                    else:
                        if is_fastest and is_shortest:
                            label = "Fastest & Shortest"
                        elif is_fastest:
                            label = "Fastest"
                        elif is_shortest:
                            label = "Shortest"
                        else:
                            label = "Alternative"

                    r["label"] = label
                    r["is_recommended"] = is_recommended
                    r["is_fastest"] = is_fastest
                    r["is_shortest"] = is_shortest
                    normalized_routes.append(r)

                primary = normalized_routes[0]

                return {
                    "success": True,
                    "routes": normalized_routes,
                    "geometry": primary["geometry"],
                    "distance_km": primary["distance_km"],
                    "duration_mins": primary["duration_mins"],
                    "raw": res_data,
                }
            else:
                logger.error(f"ORS API status error {response.status}")
                raise ValueError(f"OpenRouteService returned status code {response.status}")
    except Exception as e:
        logger.error(f"Error fetching ORS route: {e}")
        return {
            "success": False,
            "error": "Could not calculate route. Please verify your selected pickup and drop locations.",
            "routes": [],
        }



def geocode_location(query):
    """
    Geocodes a search string into [{lat, lng, display_name, short_name}, ...].
    Uses progressive query attempt fallbacks to ensure multi-word / detailed address strings always return locations.
    """
    if not query or not query.strip():
        return []

    clean_query = query.strip()
    words = [w.strip() for w in clean_query.split() if w.strip()]

    attempts = [clean_query]

    if ',' in clean_query:
        parts = [p.strip() for p in clean_query.split(',') if p.strip()]
        if len(parts) > 1:
            attempts.append(parts[0])
            attempts.append(', '.join(parts[:-1]))

    if len(words) >= 3:
        chunked = ', '.join([' '.join(words[i:i+2]) for i in range(0, len(words), 2)])
        attempts.append(chunked)
        attempts.append(' '.join(words[-3:]))
        attempts.append(' '.join(words[-2:]))

    unique_attempts = []
    for att in attempts:
        if att and att not in unique_attempts:
            unique_attempts.append(att)

    results = []
    seen_coords = set()

    for att in unique_attempts:
        try:
            params = urllib.parse.urlencode({
                "format": "json",
                "q": att,
                "countrycodes": "in",
                "addressdetails": 1,
                "limit": 8
            })
            url = f"https://nominatim.openstreetmap.org/search?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "Kaapool-Carpool-App/1.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    for place in data:
                        lat = float(place.get("lat"))
                        lng = float(place.get("lon"))
                        coord_key = (round(lat, 4), round(lng, 4))
                        if coord_key not in seen_coords:
                            seen_coords.add(coord_key)
                            full_name = place.get("display_name", "")
                            short_parts = full_name.split(",")[:3]
                            results.append({
                                "display_name": full_name,
                                "short_name": ", ".join(short_parts).strip(),
                                "lat": lat,
                                "lng": lng,
                            })
                    if results:
                        return results
        except Exception as e:
            logger.error(f"Geocode attempt '{att}' failed: {e}")

    return results



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
    import math
    lng1, lat1 = coord1
    lng2, lat2 = coord2
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def get_osrm_directions(origin_lat, origin_lng, dest_lat, dest_lng, alternatives=True):
    """
    Calculates driving route using OSRM (Open Source Routing Machine) API over OpenStreetMap data.
    OSRM URL format: https://router.project-osrm.org/route/v1/driving/{orig_lng},{orig_lat};{dest_lng},{dest_lat}?overview=full&geometries=geojson&alternatives=true
    Returns normalized route list: [{ id, distanceKm, durationMin, summary, hasTolls, geometry }, ...]
    """
    coord_str = f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
    alt_param = "true" if alternatives else "false"
    url = f"https://router.project-osrm.org/route/v1/driving/{coord_str}?overview=full&geometries=geojson&alternatives={alt_param}&steps=true"

    headers = {"User-Agent": "Kaapool-Carpool-App/1.0 (contact@kaapool.com)"}
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if data.get('code') == 'Ok':
                    osrm_routes = data.get('routes', [])
                    results = []
                    for idx, r in enumerate(osrm_routes[:4]):
                        dist_m = r.get('distance', 0.0)
                        dur_s = r.get('duration', 0.0)
                        geom = r.get('geometry', {})

                        dist_km = round(dist_m / 1000.0, 1)
                        dur_mins = max(1, round(dur_s / 60.0))

                        legs = r.get('legs', [])
                        summary = legs[0].get('summary', '') if legs else ''
                        if not summary:
                            summary = f"Route {idx + 1}"

                        results.append({
                            'id': idx,
                            'distanceKm': dist_km,
                            'durationMin': dur_mins,
                            'summary': summary,
                            'hasTolls': False,
                            'geometry': geom
                        })
                    return results
    except Exception as e:
        logger.error(f"OSRM directions call error: {e}")
    return []

