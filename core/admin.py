from django.contrib import admin
from .models import Customer, FoodItem, FoodOrder, OrderItem

admin.site.register([Customer, FoodItem, FoodOrder, OrderItem])
