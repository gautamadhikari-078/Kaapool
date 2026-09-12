from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.rides.models import Ride
import datetime

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed initial active rides into database for dynamic carpool search testing.'

    def handle(self, *args, **options):
        # Create test drivers
        driver1, _ = User.objects.get_or_create(
            username='vikas_driver',
            defaults={
                'first_name': 'Vikas',
                'last_name': 'Sharma',
                'email': 'vikas@kaapool.com',
                'is_verified_driver': True,
                'phone_number': '+91 98765 43210'
            }
        )
        if not driver1.password:
            driver1.set_password('password123')
            driver1.save()

        driver2, _ = User.objects.get_or_create(
            username='shri_driver',
            defaults={
                'first_name': 'Shri',
                'last_name': 'Ram',
                'email': 'shri@kaapool.com',
                'is_verified_driver': True,
                'phone_number': '+91 98765 12345'
            }
        )
        if not driver2.password:
            driver2.set_password('password123')
            driver2.save()

        driver3, _ = User.objects.get_or_create(
            username='ananya_driver',
            defaults={
                'first_name': 'Ananya',
                'last_name': 'Verma',
                'email': 'ananya@kaapool.com',
                'is_verified_driver': True,
                'phone_number': '+91 98765 99999'
            }
        )
        if not driver3.password:
            driver3.set_password('password123')
            driver3.save()

        now = timezone.now()
        today_date = now.date()

        sample_rides_data = [
            # Gurgaon > Rohtak (matching reference UI image!)
            {
                'driver': driver1,
                'origin': 'Gurgaon',
                'destination': 'Rohtak',
                'pickup_point': 'IFCCO Chowk / Gurugram Metro Station',
                'departure_time': timezone.make_aware(datetime.datetime.combine(today_date, datetime.time(17, 50))),
                'available_seats': 3,
                'price_per_seat': 150.00,
                'vehicle_info': 'Honda City (White) - HR26 AB 1234',
                'notes': 'Comfortable AC Sedan. Instant booking enabled.'
            },
            {
                'driver': driver2,
                'origin': 'Gurgaon',
                'destination': 'Rohtak',
                'pickup_point': 'Shahpur Bus Stand / Cyber City',
                'departure_time': timezone.make_aware(datetime.datetime.combine(today_date, datetime.time(16, 30))),
                'available_seats': 2,
                'price_per_seat': 160.00,
                'vehicle_info': 'Hyundai Creta - HR26 CD 5678',
                'notes': 'Spacious SUV, non-smoking.'
            },
            {
                'driver': driver3,
                'origin': 'Gurgaon',
                'destination': 'Rohtak',
                'pickup_point': 'Rajiv Chowk, Gurgaon',
                'departure_time': timezone.make_aware(datetime.datetime.combine(today_date + datetime.timedelta(days=1), datetime.time(9, 15))),
                'available_seats': 4,
                'price_per_seat': 180.00,
                'vehicle_info': 'Maruti Baleno - HR26 EF 9012',
                'notes': 'Morning commute, flexible pickup.'
            },
            # Delhi > Jaipur
            {
                'driver': driver1,
                'origin': 'Delhi',
                'destination': 'Jaipur',
                'pickup_point': 'Dhaula Kuan / Mahipalpur Highway',
                'departure_time': timezone.make_aware(datetime.datetime.combine(today_date, datetime.time(7, 0))),
                'available_seats': 3,
                'price_per_seat': 450.00,
                'vehicle_info': 'Toyota Innova Crysta',
                'notes': 'Highway express drive, music on board.'
            },
            {
                'driver': driver2,
                'origin': 'Delhi',
                'destination': 'Jaipur',
                'pickup_point': 'Iffco Chowk / Gurgaon Toll',
                'departure_time': timezone.make_aware(datetime.datetime.combine(today_date + datetime.timedelta(days=1), datetime.time(14, 0))),
                'available_seats': 2,
                'price_per_seat': 480.00,
                'vehicle_info': 'Honda City',
                'notes': 'Comfortable AC trip.'
            },
            # Mumbai > Pune
            {
                'driver': driver3,
                'origin': 'Mumbai',
                'destination': 'Pune',
                'pickup_point': 'Vashi Plaza / Navi Mumbai Expressway',
                'departure_time': timezone.make_aware(datetime.datetime.combine(today_date, datetime.time(18, 0))),
                'available_seats': 3,
                'price_per_seat': 350.00,
                'vehicle_info': 'Tata Nexon EV',
                'notes': 'Silent smooth EV drive.'
            },
            # Bangalore > Mysore
            {
                'driver': driver1,
                'origin': 'Bangalore',
                'destination': 'Mysore',
                'pickup_point': 'Silk Board / Kengeri Expressway',
                'departure_time': timezone.make_aware(datetime.datetime.combine(today_date, datetime.time(8, 30))),
                'available_seats': 4,
                'price_per_seat': 300.00,
                'vehicle_info': 'Kia Seltos',
                'notes': 'Smooth expressway ride.'
            }
        ]

        created_count = 0
        for item in sample_rides_data:
            ride, created = Ride.objects.get_or_create(
                driver=item['driver'],
                origin=item['origin'],
                destination=item['destination'],
                departure_time=item['departure_time'],
                defaults=item
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {created_count} dynamic sample rides!'))
