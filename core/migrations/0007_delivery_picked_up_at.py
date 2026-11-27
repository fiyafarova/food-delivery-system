"""Delivery.picked_up_at: when the courier pressed "Picked up" (see core/delivery.py).

The column is added with IF NOT EXISTS: local databases that ran an early version
of the courier branch already have it; the shared database and new databases do not.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_foodorder_discount_amount_foodorder_promo_code_promo'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "ALTER TABLE delivery ADD COLUMN IF NOT EXISTS picked_up_at timestamp with time zone NULL",
                    reverse_sql="ALTER TABLE delivery DROP COLUMN IF EXISTS picked_up_at",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='delivery',
                    name='picked_up_at',
                    field=models.DateTimeField(blank=True, null=True),
                ),
            ],
        ),
    ]
