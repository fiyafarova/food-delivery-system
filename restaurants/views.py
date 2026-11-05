from django.db.models import Q
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import RestaurantFilter, FoodItemFilter
from .models import Category, Restaurant, FoodItem
from .permissions import IsAdminOrReadOnly, IsOwnerOrReadOnly
from .serializers import CategorySerializer, RestaurantSerializer, FoodItemSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['name']
    pagination_class = None


class RestaurantViewSet(viewsets.ModelViewSet):
    queryset = Restaurant.objects.select_related('owner')
    serializer_class = RestaurantSerializer
    permission_classes = [IsOwnerOrReadOnly]
    filterset_class = RestaurantFilter
    search_fields = ['name', 'cuisine', 'description', 'address', 'city']
    ordering_fields = ['name', 'created_at']

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=False, permission_classes=[permissions.IsAuthenticated])
    def mine(self, request):
        """GET /api/restaurants/mine/ - restaurants owned by the current user."""
        qs = self.filter_queryset(self.get_queryset().filter(owner=request.user))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=True)
    def menu(self, request, pk=None):
        """GET /api/restaurants/<id>/menu/ - available food items grouped as a flat list."""
        items = FoodItem.objects.filter(restaurant=self.get_object(), is_available=True) \
                                .select_related('category', 'restaurant')
        return Response(FoodItemSerializer(items, many=True, context={'request': request}).data)


class FoodItemViewSet(viewsets.ModelViewSet):
    queryset = FoodItem.objects.select_related('restaurant', 'category')
    serializer_class = FoodItemSerializer
    permission_classes = [IsOwnerOrReadOnly]
    filterset_class = FoodItemFilter
    search_fields = ['name', 'description', 'category__name', 'restaurant__name']
    ordering_fields = ['name', 'price', 'created_at']


class GlobalSearchView(APIView):
    """GET /api/search/?q=pizza  ->  matching restaurants AND food items."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if not q:
            return Response({'detail': 'Provide a search term with ?q='}, status=400)

        restaurants = Restaurant.objects.filter(
            Q(name__icontains=q) | Q(cuisine__icontains=q) |
            Q(description__icontains=q) | Q(city__icontains=q)
        )[:20]
        foods = FoodItem.objects.select_related('restaurant', 'category').filter(
            Q(name__icontains=q) | Q(description__icontains=q) |
            Q(category__name__icontains=q) | Q(restaurant__name__icontains=q),
            is_available=True,
        )[:20]
        ctx = {'request': request}
        return Response({
            'query': q,
            'restaurants': RestaurantSerializer(restaurants, many=True, context=ctx).data,
            'food_items': FoodItemSerializer(foods, many=True, context=ctx).data,
        })
