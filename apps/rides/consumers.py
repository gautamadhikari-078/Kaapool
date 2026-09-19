import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Ride
from .services.routing import get_ors_directions, calculate_haversine_distance

logger = logging.getLogger(__name__)


class RideTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.ride_id = self.scope['url_route']['kwargs']['ride_id']
        self.room_group_name = f'ride_{self.ride_id}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action_type = data.get('type')

            if action_type == 'location_update':
                lat = float(data.get('lat'))
                lng = float(data.get('lng'))
                timestamp = data.get('timestamp')

                # Update ride model in database & compute throttled ETA
                update_res = await self.process_location_update(self.ride_id, lat, lng, timestamp)

                # Broadcast live location and updated ETA to all passengers in room
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'location_broadcast',
                        'lat': lat,
                        'lng': lng,
                        'timestamp': timestamp,
                        'remaining_distance_km': update_res.get('remaining_distance_km'),
                        'remaining_duration_mins': update_res.get('remaining_duration_mins'),
                        'status': update_res.get('status'),
                    }
                )

        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")

    async def location_broadcast(self, event):
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'lat': event['lat'],
            'lng': event['lng'],
            'timestamp': event['timestamp'],
            'remaining_distance_km': event.get('remaining_distance_km'),
            'remaining_duration_mins': event.get('remaining_duration_mins'),
            'status': event.get('status'),
        }))

    @database_sync_to_async
    def process_location_update(self, ride_id, lat, lng, timestamp):
        try:
            ride = Ride.objects.get(id=ride_id)
            now = timezone.now()

            ride.current_driver_lat = lat
            ride.current_driver_lng = lng

            # Append to actual GPS track
            if not isinstance(ride.actual_gps_track, list):
                ride.actual_gps_track = []
            ride.actual_gps_track.append({
                'lat': lat,
                'lng': lng,
                'timestamp': timestamp or now.isoformat()
            })

            remaining_dist = ride.estimated_distance_km
            remaining_dur = ride.estimated_duration_mins

            # Throttle ORS ETA recalculation (recalculate if last update was > 15s ago or driver moved > 200m)
            should_recalc = False
            if not ride.last_location_update or (now - ride.last_location_update).total_seconds() >= 15:
                should_recalc = True

            if should_recalc and ride.drop_latitude and ride.drop_longitude:
                try:
                    ors_res = get_ors_directions([[lng, lat], [ride.drop_longitude, ride.drop_latitude]])
                    if ors_res.get('success'):
                        remaining_dist = ors_res.get('distance_km')
                        remaining_dur = ors_res.get('duration_mins')
                        ride.estimated_distance_km = remaining_dist
                        ride.estimated_duration_mins = remaining_dur
                except Exception as ex:
                    logger.warning(f"Throttled ETA recalculation error: {ex}")

            ride.last_location_update = now
            ride.save(update_fields=[
                'current_driver_lat', 'current_driver_lng', 'actual_gps_track',
                'last_location_update', 'estimated_distance_km', 'estimated_duration_mins'
            ])

            return {
                'status': ride.status,
                'remaining_distance_km': remaining_dist,
                'remaining_duration_mins': remaining_dur,
            }
        except Ride.DoesNotExist:
            return {'status': 'not_found'}
