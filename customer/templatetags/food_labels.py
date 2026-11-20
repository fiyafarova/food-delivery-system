"""Translate known menu labels while preserving the source data in the database."""
from django import template
from django.utils.translation import gettext, override

register = template.Library()

DEMO_DISH_NAMES = (
    "Margherita Pizza", "Chicken Caesar Salad", "Tiramisu", "Cola",
    "Cheeseburger", "French Fries", "Beshbarmak", "Lagman", "Samsa", "Black Tea",
    "French fries", "Lemonade", "Margherita", "Pepperoni",
    "Philadelphia rolls", "Set for two",
)


@register.filter
def food_label(value):
    return gettext(str(value)) if value else ""


@register.simple_tag
def food_name_translations():
    # Favorites saved before localization may contain either English or Russian names.
    current = {name: gettext(name) for name in DEMO_DISH_NAMES}
    with override("ru"):
        russian = {name: gettext(name) for name in DEMO_DISH_NAMES}
    return {**current, **{russian[name]: current[name] for name in DEMO_DISH_NAMES}}
