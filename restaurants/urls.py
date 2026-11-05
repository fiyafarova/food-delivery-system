from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, RestaurantViewSet, FoodItemViewSet, GlobalSearchView

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('restaurants', RestaurantViewSet, basename='restaurant')
router.register('foods', FoodItemViewSet, basename='food')

urlpatterns = [
    path('search/', GlobalSearchView.as_view(), name='search'),
    path('', include(router.urls)),
]
