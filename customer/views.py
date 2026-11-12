"""Client pages. Owner: Sofiya.

Until the models are ready, views pass test data to the templates.
"""

from django.shortcuts import render
from core.models import FoodItem

def menu(request):
    items = FoodItem.objects.order_by("category", "name")
    return render(request, "customer/menu.html", {"items": items})


def cart(request):
    return render(request, "customer/cart.html")


def checkout(request):
    return render(request, "customer/checkout.html")


def order_status(request, order_id):
    return render(request, "customer/order_status.html", {"order_id": order_id})

def favorites(request):
    return render(request, "customer/favorites.html")


def profile(request):
    return render(request, "customer/profile.html")