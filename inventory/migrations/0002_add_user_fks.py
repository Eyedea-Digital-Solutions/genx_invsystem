import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Adds the user FK fields that couldn't be in 0001 due to the circular
    dependency. Now that users.0001_initial has run, it's safe to add them.
    """

    dependencies = [
        ('inventory', '0001_initial'),
        ('users', '0001_initial'),  # Safe here — no cycle, users depends on inventory.0001
    ]

    operations = [
        migrations.AddField(
            model_name='stocktake',
            name='conducted_by',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='stock_takes_conducted',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='stocktransfer',
            name='transferred_by',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='stock_transfers',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]