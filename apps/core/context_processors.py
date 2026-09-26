from django.conf import settings

def map_settings(request):
    """
    Context processor to inject map tile configuration across all templates.
    """
    return {
        'map_tile_url': getattr(settings, 'MAP_TILE_URL', 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}'),
        'map_tile_attribution': getattr(
            settings, 
            'MAP_TILE_ATTRIBUTION', 
            'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, Intermap, iPC, NRCAN, Esri Japan, METI, Esri China (Hong Kong), Esri (Thailand), TomTom, 2012'
        ),
    }
