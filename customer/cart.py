from decimal import Decimal
from types import SimpleNamespace

from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _

from restaurants.models import FoodItem

CART_KEY = "cart"
MAX_QTY = 20
DEMO_DISHES = {
    -1: (-1, "Urban Burger", _("Cheeseburger"), 1800),
    -2: (-1, "Urban Burger", _("French fries"), 900),
    -3: (-1, "Urban Burger", _("Lemonade"), 700),
    -4: (-2, "Casa Pizza", _("Margherita"), 2500),
    -5: (-2, "Casa Pizza", _("Pepperoni"), 2900),
    -6: (-2, "Casa Pizza", _("Lemonade"), 900),
    -7: (-3, "Nori Sushi", _("Philadelphia rolls"), 3200),
    -8: (-3, "Nori Sushi", _("Set for two"), 6900),
}

DEMO_DELIVERY = {-1: 400, -2: 500, -3: 600}
DEMO_PHOTOS = {
    -1: "promo-burger.jpeg",
    -2: "promo-burger.jpeg",
    -4: "promo-pizza.jpg",
    -5: "promo-pizza.jpg",
    -7: "promo-sushi.jpg",
    -8: "promo-sushi.jpg",
}


def demo_dish(dish_id):
    entry = DEMO_DISHES.get(dish_id)
    if entry is None:
        return None
    restaurant_id, restaurant_name, name, price = entry
    return SimpleNamespace(
        pk=dish_id,
        restaurant_id=restaurant_id,
        restaurant=SimpleNamespace(name=restaurant_name),
        name=name,
        price=Decimal(price),
        is_available=True,
    )


def format_money(value):
    precision = 0 if value == int(value) else 2
    return format(value, f",.{precision}f").replace(",", " ") + " ₸"


def read_session(request):
    data = request.session.get(CART_KEY)
    if not isinstance(data, dict) or not isinstance(data.get("items"), dict):
        return {"restaurant_id": None, "items": {}}
    return data


def write_session(request, data):
    request.session[CART_KEY] = data
    request.session.modified = True


def clamp_quantity(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 1
    return min(max(number, 1), MAX_QTY)


def session_count(request):
    items = read_session(request)["items"]
    return sum(clamp_quantity(qty) for qty in items.values())


def add_dish(request, dish_id, replace=False):
    if dish_id < 0:
        dish = demo_dish(dish_id)
    else:
        dish = FoodItem.objects.select_related("restaurant").filter(pk=dish_id).first()
    if dish is None:
        return "not_found", {}
    if not dish.is_available:
        return "unavailable", {}

    data = read_session(request)
    current_id = data.get("restaurant_id")
    if data["items"] and current_id and current_id != dish.restaurant_id:
        if not replace:
            current = build_cart(request)
            return "conflict", {
                "current_restaurant": current["restaurant_name"],
                "new_restaurant": dish.restaurant.name,
            }
        data = {"restaurant_id": None, "items": {}}

    key = str(dish.pk)
    data["restaurant_id"] = dish.restaurant_id
    data["items"][key] = clamp_quantity(data["items"].get(key, 0) + 1)
    write_session(request, data)
    return "ok", {}


def set_quantity(request, dish_id, quantity):
    data = read_session(request)
    key = str(dish_id)
    if key not in data["items"]:
        return "not_found"
    if quantity <= 0:
        del data["items"][key]
    else:
        data["items"][key] = min(quantity, MAX_QTY)
    if not data["items"]:
        data["restaurant_id"] = None
    write_session(request, data)
    return "ok"


def clear_cart(request):
    write_session(request, {"restaurant_id": None, "items": {}})


def build_cart(request):
    data = read_session(request)
    ids = []
    for key in data["items"]:
        try:
            ids.append(int(key))
        except ValueError:
            continue

    dishes = {
        dish.pk: dish
        for dish in FoodItem.objects.select_related("restaurant").filter(pk__in=[dish_id for dish_id in ids if dish_id > 0])
    }

    lines = []
    cleaned = {}
    subtotal = Decimal("0")
    count = 0
    has_unavailable = False
    restaurant_name = ""

    for key, raw_qty in data["items"].items():
        try:
            dish_id = int(key)
            dish = demo_dish(dish_id) if dish_id < 0 else dishes.get(dish_id)
        except ValueError:
            continue
        if dish is None:
            continue
        photo = DEMO_PHOTOS.get(dish_id)
        quantity = clamp_quantity(raw_qty)
        cleaned[key] = quantity
        line_total = dish.price * quantity
        if dish.is_available:
            subtotal += line_total
        else:
            has_unavailable = True
        count += quantity
        restaurant_name = restaurant_name or dish.restaurant.name
        lines.append(
            {
                "id": dish.pk,
                "name": dish.name,
                "image_url": static(f"images/{photo}") if photo else "",
                "available": dish.is_available,
                "quantity": quantity,
                "price_display": format_money(dish.price),
                "total_display": format_money(line_total),
            }
        )

    if cleaned != data["items"]:
        data["items"] = cleaned
        if not cleaned:
            data["restaurant_id"] = None
        write_session(request, data)

    empty = not lines
    delivery = DEMO_DELIVERY.get(data.get("restaurant_id")) if lines else None
    return {
        "lines": lines,
        "empty": empty,
        "count": count,
        "restaurant_name": restaurant_name,
        "subtotal_display": format_money(subtotal),
        "subtotal_minor": int(subtotal * 100),
        "total_minor": int((subtotal + delivery) * 100) if delivery is not None else None,
        "has_unavailable": has_unavailable,
        "delivery_display": format_money(delivery) if delivery is not None else None,
        "total_display": format_money(subtotal + delivery) if delivery is not None else None,
        "can_checkout": not empty and not has_unavailable,
    }


def cart_payload(cart):
    return {
        "empty": cart["empty"],
        "count": cart["count"],
        "restaurant": cart["restaurant_name"],
        "subtotal": cart["subtotal_display"],
        "subtotal_minor": cart["subtotal_minor"],
        "total_minor": cart["total_minor"],
        "total": cart["total_display"] or cart["subtotal_display"],
        "has_unavailable": cart["has_unavailable"],
        "can_checkout": cart["can_checkout"],
        "lines": {
            str(line["id"]): {
                "quantity": line["quantity"],
                "total": line["total_display"],
            }
            for line in cart["lines"]
        },
    }
