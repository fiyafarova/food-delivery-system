"""Dishes come from restaurants.FoodItem; every order belongs to one restaurant (part 1: data).

Team decision (after the integration merge): keep restaurants.FoodItem
(Sayazhan's app, used by the customer menu and cart) and remove core.FoodItem.

Existing data is kept: if the database already has core.FoodItem rows (for
example Darya's demo data), they are copied into a restaurant "BiteBox Kitchen",
and the order lines and orders are pointed to the copies.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

LEGACY_RESTAURANT = "BiteBox Kitchen"


def move_dishes_to_restaurants(apps, schema_editor):
    OldFoodItem = apps.get_model("core", "FoodItem")
    FoodOrder = apps.get_model("core", "FoodOrder")
    OrderItem = apps.get_model("core", "OrderItem")
    Restaurant = apps.get_model("restaurants", "Restaurant")
    Category = apps.get_model("restaurants", "Category")
    NewFoodItem = apps.get_model("restaurants", "FoodItem")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))

    if not OldFoodItem.objects.exists() and not FoodOrder.objects.exists():
        return  # fresh database: nothing to move

    owner = (User.objects.filter(is_superuser=True).order_by("pk").first()
             or User.objects.filter(role__in=["owner", "admin"]).order_by("pk").first())
    if owner is None:
        owner, _ = User.objects.get_or_create(
            username="owner_demo",
            defaults={"email": "owner_demo@example.com", "role": "owner", "password": "!no-login-yet"},
        )
    restaurant, _ = Restaurant.objects.get_or_create(
        name=LEGACY_RESTAURANT,
        defaults={"owner": owner, "address": "Almaty", "city": "Almaty", "cuisine": "Mixed"},
    )

    new_ids = {}
    for old in OldFoodItem.objects.all():
        category, _ = Category.objects.get_or_create(name=old.category) if old.category else (None, False)
        new = NewFoodItem.objects.create(
            restaurant=restaurant, category=category, name=old.name,
            price=old.price, is_available=old.is_available,
        )
        new_ids[old.pk] = new.pk

    for line in OrderItem.objects.all():
        line.new_food_item_id = new_ids[line.food_item_id]
        line.save(update_fields=["new_food_item"])
    FoodOrder.objects.update(restaurant=restaurant)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("restaurants", "0003_protect_staff_price_check"),
        ("accounts", "0004_deliveryaddress_autofield"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. new nullable columns
        migrations.AddField(
            model_name="foodorder",
            name="restaurant",
            field=models.ForeignKey(
                null=True, db_column="restaurant_id", on_delete=django.db.models.deletion.PROTECT,
                related_name="orders", to="restaurants.restaurant"),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="new_food_item",
            field=models.ForeignKey(
                null=True, db_column="new_food_item_id", on_delete=django.db.models.deletion.PROTECT,
                related_name="+", to="restaurants.fooditem"),
        ),
        # 2. copy old dishes and fill the new columns
        migrations.RunPython(move_dishes_to_restaurants, migrations.RunPython.noop),
    ]
