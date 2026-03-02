import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Creates all inventory tables WITHOUT the user FK fields
    (conducted_by on StockTake, transferred_by on StockTransfer).
    Those are added in 0002 after the users app has been migrated.
    This breaks the circular dependency between inventory and users.
    """

    initial = True

    dependencies = []  # No dependency on users here — that would cause the cycle

    operations = [
        migrations.CreateModel(
            name='Joint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(
                    choices=[('eyedentity', 'Eyedentity'), ('genx', 'GenX'), ('armor_sole', 'Armor Sole')],
                    help_text='The name/identifier of this shop.',
                    max_length=50,
                    unique=True,
                )),
                ('display_name', models.CharField(max_length=100)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('address', models.TextField(blank=True)),
                ('uses_product_codes', models.BooleanField(default=False)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(blank=True, max_length=50, null=True)),
                ('name', models.CharField(max_length=200)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('joint', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='products',
                    to='inventory.joint',
                )),
            ],
            options={'ordering': ['joint', 'name']},
        ),
        migrations.AlterUniqueTogether(
            name='product',
            unique_together={('joint', 'code')},
        ),
        migrations.CreateModel(
            name='Stock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField(default=0)),
                ('last_stock_take', models.DateTimeField(blank=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('product', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock',
                    to='inventory.product',
                )),
            ],
            options={'verbose_name': 'Stock Level'},
        ),
        migrations.CreateModel(
            name='StockTake',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('conducted_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('notes', models.TextField(blank=True)),
                # conducted_by (FK to users.User) is added in 0002
                ('joint', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock_takes',
                    to='inventory.joint',
                )),
            ],
            options={'ordering': ['-conducted_at']},
        ),
        migrations.CreateModel(
            name='StockTakeItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('system_count', models.IntegerField()),
                ('actual_count', models.IntegerField()),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='inventory.product',
                )),
                ('stock_take', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                    to='inventory.stocktake',
                )),
            ],
        ),
        migrations.CreateModel(
            name='StockTransfer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField()),
                ('transferred_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('completed', 'Completed')],
                    default='pending',
                    max_length=20,
                )),
                ('notes', models.TextField(blank=True)),
                # transferred_by (FK to users.User) is added in 0002
                ('from_joint', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='transfers_out',
                    to='inventory.joint',
                )),
                ('to_joint', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='transfers_in',
                    to='inventory.joint',
                )),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='inventory.product',
                )),
            ],
            options={'ordering': ['-transferred_at']},
        ),
    ]