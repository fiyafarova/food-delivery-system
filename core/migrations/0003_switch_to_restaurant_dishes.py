"""Dishes come from restaurants.FoodItem (part 2: switch the columns, drop core.FoodItem).

Separate from 0002 because PostgreSQL cannot change a table in the same
transaction that has just inserted rows into it ("pending trigger events").
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_dishes_from_restaurants"),
    ]

    operations = [
        # 3. replace the old dish column with the new one
        migrations.RemoveConstraint(model_name="orderitem", name="uq_order_food"),
        migrations.RemoveField(model_name="orderitem", name="food_item"),
        migrations.RenameField(model_name="orderitem", old_name="new_food_item", new_name="food_item"),
        migrations.AlterField(
            model_name="orderitem",
            name="food_item",
            field=models.ForeignKey(
                db_column="food_item_id", on_delete=django.db.models.deletion.PROTECT,
                related_name="order_items", to="restaurants.fooditem"),
        ),
        migrations.AddConstraint(
            model_name="orderitem",
            constraint=models.UniqueConstraint(fields=("order", "food_item"), name="uq_order_food"),
        ),
        migrations.AlterField(
            model_name="foodorder",
            name="restaurant",
            field=models.ForeignKey(
                db_column="restaurant_id", on_delete=django.db.models.deletion.PROTECT,
                related_name="orders", to="restaurants.restaurant"),
        ),
        # 4. the old dish table is no longer used
        migrations.DeleteModel(name="FoodItem"),
    ]
