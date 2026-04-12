from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Employee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('email', models.EmailField(blank=True)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('role', models.CharField(choices=[('cashier', 'Cashier'), ('manager', 'Manager'), ('supervisor', 'Supervisor'), ('stock_controller', 'Stock Controller'), ('accountant', 'Accountant'), ('admin', 'Admin')], default='cashier', max_length=30)),
                ('branch', models.CharField(blank=True, max_length=100)),
                ('date_joined', models.DateField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='employee_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['last_name', 'first_name']},
        ),
    ]
