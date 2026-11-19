"""Budget meal preview. Remove this module and its URL to remove the feature."""
from decimal import Decimal, InvalidOperation
from itertools import islice

from django.conf import settings
from django.contrib import messages
from django.core import signing
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _, gettext_lazy
from django.views.decorators.http import require_http_methods

from restaurants.models import FoodItem, Restaurant
from .cart import format_money, read_session, write_session

# Until restaurant tariffs are added, the preview explicitly labels this as a test fee.
DEFAULT_DELIVERY_FEE = Decimal("500")
PAGE_SIZE = 12
CATEGORIES = {
    "main": ({"main course", "main", "pizza", "burgers", "sushi", "основное блюдо", "основные блюда", "salad", "salads", "салат", "салаты", "пицца", "бургеры", "суши"}, gettext_lazy("Main dish")),
    "drink": ({"drinks", "drink", "beverages", "напитки", "напиток"}, gettext_lazy("Drink")),
    "snack": ({"snacks", "snack", "appetizers", "закуски", "закуска", "sides", "side", "side dishes", "гарнир", "гарниры"}, gettext_lazy("Snack")),
    "dessert": ({"desserts", "dessert", "десерты", "десерт"}, gettext_lazy("Dessert")),
}


def delivery_fee():
    return Decimal(str(getattr(settings, "BUDGET_PREVIEW_DELIVERY_FEE", DEFAULT_DELIVERY_FEE)))


def combinations(pools, remaining, selected=()):
    if not pools:
        yield selected
        return
    for dish in pools[0]:
        if dish.price > remaining:
            break
        yield from combinations(pools[1:], remaining - dish.price, selected + (dish,))


def results(restaurants, selected, budget, fee):
    for restaurant in restaurants:
        pools = []
        for key in selected:
            names = CATEGORIES[key][0]
            dishes = [dish for dish in restaurant.food_items.all()
                      if dish.is_available and dish.category
                      and dish.category.name.strip().casefold() in names]
            pools.append(sorted(dishes, key=lambda dish: (dish.price, dish.pk)))
        for dishes in combinations(pools, budget - fee):
            subtotal = sum((dish.price for dish in dishes), Decimal("0"))
            yield {
                "restaurant": restaurant,
                "dishes": [{"name": dish.name, "description": dish.description, "price": format_money(dish.price)}
                           for dish in dishes],
                "subtotal": format_money(subtotal),
                "total": format_money(subtotal + fee),
                "token": signing.dumps({"ids": [dish.pk for dish in dishes], "budget": str(budget)},
                                       salt="budget-meal"),
            }


def add_bundle(request):
    try:
        data = signing.loads(request.POST.get("bundle", ""), salt="budget-meal", max_age=3600)
        ids = data["ids"]
        budget = Decimal(data["budget"])
        dishes = list(FoodItem.objects.select_related("restaurant").filter(
            pk__in=ids, is_available=True, restaurant__is_open=True))
        if len(dishes) != len(ids) or not dishes:
            raise ValueError
        restaurants = {dish.restaurant_id for dish in dishes}
        if len(restaurants) != 1:
            raise ValueError
        total = sum((dish.price for dish in dishes), Decimal("0")) + delivery_fee()
        if total > budget:
            raise ValueError
    except (signing.BadSignature, KeyError, ValueError, TypeError, InvalidOperation):
        messages.error(request, _("This set has changed or expired. Please select it again."))
        return redirect("customer:budget")

    current = read_session(request)
    # Replacing the cart also keeps its full total within the selected budget.
    if current["items"] and request.POST.get("replace") != "1":
        return render(request, "customer/budget_confirm.html", {
            "bundle": request.POST["bundle"], "restaurant": dishes[0].restaurant,
        })
    write_session(request, {"restaurant_id": dishes[0].restaurant_id,
                            "items": {str(dish.pk): 1 for dish in dishes}})
    return redirect("customer:cart")


@require_http_methods(["GET", "POST"])
def budget_meals(request):
    if request.method == "POST":
        return add_bundle(request)
    selected = list(dict.fromkeys(request.GET.getlist("part"))) if request.GET else ["main", "drink"]
    selected = [key for key in selected if key in CATEGORIES]
    fee = delivery_fee()
    context = {"choices": [(key, label, key in selected) for key, (_names, label) in CATEGORIES.items()],
               "fee": format_money(fee), "budget": request.GET.get("budget", ""),
               "cuisine": request.GET.get("cuisine", ""),
               "cuisines": Restaurant.objects.filter(is_open=True).exclude(cuisine="").values_list("cuisine", flat=True).distinct().order_by("cuisine"),
               "submitted": bool(request.GET)}
    if request.GET:
        try:
            budget = Decimal(context["budget"].replace(",", "."))
            if not budget.is_finite() or budget <= 0 or budget > Decimal("1000000") or budget.as_tuple().exponent < -2:
                raise ValueError
            if not selected:
                context["error"] = _("Choose at least one part of your meal.")
            else:
                restaurants = Restaurant.objects.filter(is_open=True).prefetch_related("food_items__category").order_by("name", "pk")
                if context["cuisine"]:
                    restaurants = restaurants.filter(cuisine=context["cuisine"])
                try:
                    page = max(1, int(request.GET.get("page", "1")))
                except ValueError:
                    page = 1
                matches = list(islice(results(restaurants, selected, budget, fee),
                                      (page - 1) * PAGE_SIZE, page * PAGE_SIZE + 1))
                context["matches"] = matches[:PAGE_SIZE]
                query = request.GET.copy()
                if page > 1:
                    query["page"] = page - 1
                    context["previous"] = "?" + query.urlencode()
                if len(matches) > PAGE_SIZE:
                    query["page"] = page + 1
                    context["next"] = "?" + query.urlencode()
        except (InvalidOperation, ValueError):
            context["error"] = _("Enter a budget between 1 and 1,000,000 tenge, with up to two decimal places.")
    return render(request, "customer/budget.html", context)
