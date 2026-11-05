"""Temporary test data for the staff pages.

Replace it with queries to core.models (Food_Order, Order_Item, Food_Item)
when the backend models are ready.
"""


def make_orders():
    return [
        {"id": 101, "customer": "Aigerim", "phone": "+7 701 111 11 11", "address": "Abay 1, Almaty",
         "status": "Placed",
         "items": [{"name": "Pizza", "quantity": 2, "unit_price": 2500},
                   {"name": "Burger", "quantity": 1, "unit_price": 1800}]},
        {"id": 102, "customer": "Aidos", "phone": "+7 702 222 22 22", "address": "Satpaev 5, Almaty",
         "status": "Preparing",
         "items": [{"name": "Burger", "quantity": 1, "unit_price": 1800}]},
        {"id": 103, "customer": "Dana", "phone": "+7 705 333 33 33", "address": "Dostyk 10, Almaty",
         "status": "Delivered",
         "items": [{"name": "Pizza", "quantity": 1, "unit_price": 2500}]},
        {"id": 104, "customer": "Marat", "phone": "+7 707 444 44 44", "address": "Nazarbayev 3, Almaty",
         "status": "Cancelled",
         "items": [{"name": "Cola", "quantity": 2, "unit_price": 600}]},
    ]


def make_menu():
    return [
        {"id": 1, "name": "Pizza", "price": 2500, "category": "Main", "is_available": True},
        {"id": 2, "name": "Burger", "price": 1800, "category": "Main", "is_available": True},
        {"id": 3, "name": "Cola", "price": 600, "category": "Drinks", "is_available": False},
    ]