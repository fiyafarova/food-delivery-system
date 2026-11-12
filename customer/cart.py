from decimal import Decimal

from restaurants.models import FoodItem

CART_KEY = "cart"
MAX_QTY = 20


def format_money(value):
    return "{:,.0f}".format(value).replace(",", " ") + " ₸"


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
        for dish in FoodItem.objects.select_related("restaurant").filter(pk__in=ids)
    }

    lines = []
    cleaned = {}
    subtotal = Decimal("0")
    count = 0
    has_unavailable = False
    restaurant_name = ""

    for key, raw_qty in data["items"].items():
        try:
            dish = dishes.get(int(key))
        except ValueError:
            continue
        if dish is None:
            continue
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
                "image_url": "",
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
    return {
        "lines": lines,
        "empty": empty,
        "count": count,
        "restaurant_name": restaurant_name,
        "subtotal_display": format_money(subtotal),
        "has_unavailable": has_unavailable,
        "can_checkout": not empty and not has_unavailable,
    }


def cart_payload(cart):
    return {
        "empty": cart["empty"],
        "count": cart["count"],
        "restaurant": cart["restaurant_name"],
        "subtotal": cart["subtotal_display"],
        "total": cart["subtotal_display"],
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