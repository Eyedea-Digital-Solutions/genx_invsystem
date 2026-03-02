"""
Management command to set up the initial data for the system.

Run with: python manage.py setup_initial_data

This creates:
- The 3 joints (Eyedentity, GenX, Armor Sole)
- An admin user

Run this ONCE after your first migrate.
"""

from django.core.management.base import BaseCommand
from inventory.models import Joint


class Command(BaseCommand):
    help = 'Set up initial joints (shops) for the inventory system'

    def handle(self, *args, **options):
        self.stdout.write('Setting up initial data...')

        # Create the 3 joints
        joints = [
            {
                'name': 'eyedentity',
                'display_name': 'Eyedentity - Zee Eyewear',
                'phone': '+263 775 897 955',
                'address': 'Shop 15, Summer City Mall, 63 Speke Avenue, Harare',
                'uses_product_codes': True,
            },
            {
                'name': 'genx',
                'display_name': 'GenX Zimbabwe',
                'phone': '+263 775 897 955',
                'address': 'Shop 15, Summer City Mall, 63 Speke Avenue, Harare',
                'uses_product_codes': False,
            },
            {
                'name': 'armor_sole',
                'display_name': 'Armor Sole',
                'phone': '+263784758822',
                'address': 'Shop 15, Summer City Mall, 63 Speke Avenue, Harare',
                'uses_product_codes': True,
            },
        ]

        for joint_data in joints:
            joint, created = Joint.objects.get_or_create(
                name=joint_data['name'],
                defaults=joint_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created joint: {joint.display_name}'))
            else:
                self.stdout.write(f'  - Joint already exists: {joint.display_name}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✓ Initial data setup complete!'))
        self.stdout.write('')
        self.stdout.write('Next steps:')
        self.stdout.write('  1. Create a superuser: python manage.py createsuperuser')
        self.stdout.write('  2. Run the server: python manage.py runserver')
        self.stdout.write('  3. Log in and start adding products!')
