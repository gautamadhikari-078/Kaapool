from django.db import migrations, models


def migrate_active_to_scheduled(apps, schema_editor):
    Ride = apps.get_model('rides', 'Ride')
    Ride.objects.filter(status='active').update(status='scheduled')


class Migration(migrations.Migration):

    dependencies = [
        ('rides', '0005_vehicle_features'),
    ]

    operations = [
        migrations.RenameField(
            model_name='ride',
            old_name='departure_time',
            new_name='departure_datetime',
        ),
        migrations.AlterModelOptions(
            name='ride',
            options={'ordering': ['-departure_datetime']},
        ),
        migrations.AlterField(
            model_name='ride',
            name='departure_datetime',
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name='ride',
            name='status',
            field=models.CharField(
                choices=[
                    ('scheduled', 'Scheduled'),
                    ('in_progress', 'In Progress'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                    ('expired', 'Expired'),
                    ('active', 'Active'),
                ],
                default='scheduled',
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name='ride',
            index=models.Index(fields=['driver', 'departure_datetime'], name='ride_driver_dep_idx'),
        ),
        migrations.AddIndex(
            model_name='ride',
            index=models.Index(fields=['driver', 'status'], name='ride_driver_status_idx'),
        ),
        migrations.RunPython(migrate_active_to_scheduled, reverse_code=migrations.RunPython.noop),
    ]
