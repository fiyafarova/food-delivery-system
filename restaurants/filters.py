import django_filters

from .models import Restaurant, FoodItem


class RestaurantFilter(django_filters.FilterSet):
    city = django_filters.CharFilter(field_name='city', lookup_expr='iexact')
    cuisine = django_filters.CharFilter(field_name='cuisine', lookup_expr='icontains')

    class Meta:
        model = Restaurant
        fields = ['city', 'cuisine', 'is_open']


class FoodItemFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')

    class Meta:
        model = FoodItem
        fields = ['restaurant', 'category', 'is_available', 'min_price', 'max_price']
