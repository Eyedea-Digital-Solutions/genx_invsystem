from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Creates the default admin superuser non-interactively'

    def handle(self, *args, **options):
        User = get_user_model()

        username = 'admin'
        password = 'admin1234'
        email = 'admin@genx.com'

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(
                f'User "{username}" already exists. Skipping.'
            ))
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            role='admin',
        )

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Superuser created!'
            f'\n  Username: {username}'
            f'\n  Password: {password}'
            f'\n  Email:    {email}'
            f'\n\n  Please change the password after logging in at /admin/'
        ))