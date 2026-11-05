from rest_framework import serializers

from .models import Category, Restaurant, FoodItem


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'description')


class RestaurantSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = Restaurant
        fields = ('id', 'owner', 'name', 'description', 'cuisine', 'address',
                  'city', 'phone', 'is_open', 'created_at')
        read_only_fields = ('created_at',)


class FoodItemSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    restaurant_name = serializers.ReadOnlyField(source='restaurant.name')

    class Meta:
        model = FoodItem
        fields = ('id', 'restaurant', 'restaurant_name', 'category', 'category_name',
                  'name', 'description', 'price', 'is_available', 'created_at')
        read_only_fields = ('created_at',)

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError('Price must be greater than 0.')
        return value

    def validate_restaurant(self, restaurant):
        user = self.context['request'].user
        if restaurant.owner != user and user.role != 'admin' and not user.is_superuser:
            raise serializers.ValidationError('You can only manage food in your own restaurants.')
        return restaurant
