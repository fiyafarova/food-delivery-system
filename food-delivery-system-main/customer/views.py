"""Client pages. Owner: Sofiya.

Until the models are ready, views pass test data to the templates.
"""

from django.shortcuts import render

# Temporary test data (replace with queries to core.models later)
TEST_MENU = [
    {"id": 1, "name": "Pizza", "price": 2500, "category": "Main", "is_available": True},
    {"id": 2, "name": "Burger", "price": 1800, "category": "Main", "is_available": True},
    {"id": 3, "name": "Cola", "price": 600, "category": "Drinks", "is_available": False},
]


def menu(request):
    return render(request, "customer/menu.html", {"items": TEST_MENU})


def cart(request):
    return render(request, "customer/cart.html")


def checkout(request):
    return render(request, "customer/checkout.html")


def order_status(request, order_id):
    return render(request, "customer/order_status.html", {"order_id": order_id})
