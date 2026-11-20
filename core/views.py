import json
from decimal import Decimal
from functools import wraps

from .statuses import TRANSITIONS, STATUSES



from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from django.db import transaction

from customer import cart as shared_cart
from restaurants.models import FoodItem

from .access import CustomerDataError, can_manage_order, can_view_order, customer_of, get_or_create_customer
from .models import Customer, Delivery, FoodOrder, OrderItem, Payment



from django.middleware.csrf import CsrfViewMiddleware
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

# =========================
# ACCESS CHECKS
# =========================
# Not logged in -> 401. Someone else's order -> 404 (we do not tell that it exists).
# "view": the customer who placed the order, or staff of its restaurant.
# "manage": staff / owner / admin of the order's restaurant only.

def _order_from_kwargs(kwargs):
    if "order_id" in kwargs:
        return FoodOrder.objects.filter(pk=kwargs["order_id"]).select_related("customer").first()
    if "payment_id" in kwargs:
        payment = Payment.objects.filter(pk=kwargs["payment_id"]).select_related("order__customer").first()
        return payment.order if payment else None
    if "delivery_id" in kwargs:
        delivery = Delivery.objects.filter(pk=kwargs["delivery_id"]).select_related("order__customer").first()
        return delivery.order if delivery else None
    return None


def order_access(kind):
    check = can_view_order if kind == "view" else can_manage_order

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            auth_header = request.headers.get("Authorization", "")

            if auth_header.startswith("Bearer "):
                try:
                    authentication = JWTAuthentication().authenticate(request)
                except AuthenticationFailed:
                    return JsonResponse(
                        {"error": "Invalid or expired access token."},
                        status=401
                    )

                if authentication is None:
                    return JsonResponse(
                        {"error": "Invalid access token."},
                        status=401
                    )

                request.user, request.auth = authentication

            else:
                if not request.user.is_authenticated:
                    return JsonResponse(
                        {"error": "Log in first."},
                        status=401
                    )

                csrf_middleware = CsrfViewMiddleware(lambda req: None)
                csrf_response = csrf_middleware.process_view(
                    request, view, (), kwargs
                )

                if csrf_response is not None:
                    return csrf_response

            order = _order_from_kwargs(kwargs)

            if order is None or not check(request.user, order):
                return JsonResponse({"error": "Not found."}, status=404)

            return view(request, *args, **kwargs)

        wrapper.csrf_exempt = True
        return wrapper

    return decorator
# =========================
# SHOPPING CART
# =========================
# There is ONE cart for the whole site: customer/cart.py (Dilnaz). It is stored in
# the session as {"restaurant_id": ..., "items": {dish_id: quantity}} and only
# allows dishes from one restaurant. These JSON endpoints use the same cart.


def cart_lines(request):
    """Real dishes in the cart: list of (FoodItem, quantity). Demo dishes (negative ids) are skipped."""
    items = shared_cart.read_session(request)["items"]
    ids = [int(key) for key in items if key.lstrip("-").isdigit() and int(key) > 0]
    dishes = FoodItem.objects.select_related("restaurant").in_bulk(ids)
    return [(dishes[int(key)], int(qty)) for key, qty in items.items()
            if key.lstrip("-").isdigit() and int(key) in dishes]


@require_GET
def view_cart(request):
    items = []
    total = Decimal("0.00")
    for food, quantity in cart_lines(request):
        if not food.is_available:
            continue
        subtotal = food.price * quantity
        total += subtotal
        items.append({
            "food_item_id": food.pk,
            "name": food.name,
            "price": str(food.price),
            "quantity": quantity,
            "subtotal": str(subtotal),
        })

    return JsonResponse({
        "restaurant_id": shared_cart.read_session(request).get("restaurant_id"),
        "items": items,
        "total": str(total),
    })


@require_POST
def add_to_cart(request):
    try:
        data = json.loads(request.body)
        food_id = int(data.get("food_item_id"))
        quantity = int(data.get("quantity", 1))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid request data."}, status=400)

    if quantity <= 0:
        return JsonResponse({"error": "Quantity must be greater than zero."}, status=400)

    food = get_object_or_404(FoodItem, pk=food_id, is_available=True)
    status, info = shared_cart.add_dish(request, food.pk, replace=bool(data.get("replace")))
    if status == "conflict":
        # one order = one restaurant: send "replace": true to empty the cart and start again
        return JsonResponse({
            "error": "The cart already has dishes from another restaurant.",
            **info,
        }, status=409)

    current = shared_cart.read_session(request)["items"].get(str(food.pk), 0)
    shared_cart.set_quantity(request, food.pk, current - 1 + quantity)  # add_dish added 1

    return JsonResponse({
        "message": "Item added to cart.",
        "food_item": food.name,
        "quantity": shared_cart.read_session(request)["items"][str(food.pk)],
    })


@require_POST
def update_cart(request):
    try:
        data = json.loads(request.body)
        food_id = int(data.get("food_item_id"))
        quantity = int(data.get("quantity"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid request data."}, status=400)

    if quantity <= 0:
        return JsonResponse({"error": "Quantity must be greater than zero."}, status=400)
    if shared_cart.set_quantity(request, food_id, quantity) == "not_found":
        return JsonResponse({"error": "Item is not in the cart."}, status=404)
    return JsonResponse({"message": "Cart updated."})


@require_POST
def remove_from_cart(request):
    try:
        data = json.loads(request.body)
        food_id = int(data.get("food_item_id"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid request data."}, status=400)

    if shared_cart.set_quantity(request, food_id, 0) == "not_found":
        return JsonResponse({"error": "Item is not in the cart."}, status=404)
    return JsonResponse({"message": "Item removed from cart."})


# =========================
# CREATE ORDER
# =========================

@require_POST
def create_order(request):
    """Order the cart. The customer is the logged-in account (customer_id from the body is ignored)."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Log in to place an order."}, status=401)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid order data."}, status=400)

    lines = cart_lines(request)
    if not lines:
        return JsonResponse({"error": "Your cart is empty."}, status=400)
    if any(not food.is_available for food, _qty in lines):
        return JsonResponse({"error": "Some dishes in the cart are not available."}, status=400)

    restaurants = {food.restaurant_id for food, _qty in lines}
    if len(restaurants) != 1:  # the cart never allows this, but check anyway
        return JsonResponse({"error": "All dishes must be from one restaurant."}, status=400)

    try:
        customer = get_or_create_customer(
            request.user, data.get("name", ""), data.get("phone", ""), data.get("address", ""))
    except CustomerDataError as error:
        return JsonResponse({"error": str(error)}, status=400)

    with transaction.atomic():
        order = FoodOrder.objects.create(
            customer=customer,
            restaurant_id=restaurants.pop(),
            status="Placed",
            total_amount=Decimal("0.00"),
        )
        total = Decimal("0.00")
        for food, quantity in lines:
            total += food.price * quantity
            OrderItem.objects.create(order=order, food_item=food, quantity=quantity, unit_price=food.price)
        order.total_amount = total
        order.save(update_fields=["total_amount"])

    shared_cart.clear_cart(request)

    return JsonResponse({
        "message": "Order created successfully.",
        "order_id": order.order_id,
        "restaurant": order.restaurant.name,
        "status": order.status,
        "total_amount": str(order.total_amount),
    }, status=201)


# =========================
# ORDER DETAILS
# =========================

@require_GET
@order_access("view")
def order_details(request, order_id):
    order = get_object_or_404(FoodOrder.objects.select_related("restaurant"), order_id=order_id)

    items = []
    for item in order.items.select_related("food_item"):
        items.append({
            "food_item_id": item.food_item.pk,
            "food_name": item.food_item.name,
            "quantity": item.quantity,
            "unit_price": str(item.unit_price),
            "subtotal": str(item.unit_price * item.quantity),
        })

    return JsonResponse({
        "order_id": order.order_id,
        "customer_id": order.customer.customer_id,
        "restaurant_id": order.restaurant_id,
        "restaurant": order.restaurant.name,
        "order_date": order.order_date.isoformat(),
        "status": order.status,
        "total_amount": str(order.total_amount),
        "items": items,
    })


# =========================
# ORDER STATUS
# =========================






# =========================
# ORDER HISTORY
# =========================

@require_GET
def order_history(request, customer_id):
    """History of one customer: only for that customer or an admin."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Log in first."}, status=401)
    customer = get_object_or_404(Customer, customer_id=customer_id)
    is_admin = request.user.is_superuser or request.user.role == request.user.Role.ADMIN
    if customer.user_id != request.user.pk and not is_admin:
        return JsonResponse({"error": "Not found."}, status=404)
    return JsonResponse(history_payload(customer))


@require_GET
def my_orders(request):
    """GET /core/orders/mine/ - order history of the logged-in customer."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Log in first."}, status=401)
    customer = customer_of(request.user)
    if customer is None:
        return JsonResponse({"customer_id": None, "orders": []})
    return JsonResponse(history_payload(customer))


def history_payload(customer):
    orders = FoodOrder.objects.filter(
        customer=customer
    ).order_by("-order_date")

    result = []

    for order in orders:
        result.append({
            "order_id": order.order_id,
            "restaurant": order.restaurant.name,
            "order_date": order.order_date.isoformat(),
            "status": order.status,
            "total_amount": str(order.total_amount),
            "items_count": order.items.count(),
        })

    return {
        "customer_id": customer.customer_id,
        "orders": result,
    }
from django.utils import timezone

#===============
#something new
#===============
@require_POST
@order_access("manage")
def update_order_status(request, order_id):
    try:
        data = json.loads(request.body or "{}")
        new_status = data.get("status")

        if new_status not in STATUSES:
            return JsonResponse(
                {"error": "Invalid order status."},
                status=400
            )

        order = get_object_or_404(
            FoodOrder,
            order_id=order_id
        )

        allowed_statuses = TRANSITIONS.get(order.status, [])

        if new_status not in allowed_statuses:
            return JsonResponse(
                {
                    "error": "This status transition is not allowed.",
                    "current_status": order.status,
                    "allowed_statuses": allowed_statuses,
                },
                status=400
            )

        order.status = new_status
        order.save(update_fields=["status"])

        return JsonResponse({
            "message": "Order status updated.",
            "order_id": order.order_id,
            "status": order.status,
        })

    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Invalid request data."},
            status=400
        )

# =========================
# PAYMENT MANAGEMENT
# =========================

@require_POST
@order_access("view")
def create_payment(request, order_id):
    try:
        data = json.loads(request.body)

        order = get_object_or_404(
            FoodOrder,
            order_id=order_id
        )

        if Payment.objects.filter(order=order).exists():
            return JsonResponse(
                {"error": "Payment already exists for this order."},
                status=400
            )

        method = data.get("payment_method", "Cash")

        if method not in ["Cash", "Card"]:
            return JsonResponse(
                {"error": "Invalid payment method."},
                status=400
            )

        payment = Payment.objects.create(
            order=order,
            amount=order.total_amount,
            payment_method=method,
            payment_status="Pending"
        )

        return JsonResponse({
            "message": "Payment created successfully.",
            "payment_id": payment.payment_id,
            "order_id": order.order_id,
            "amount": str(payment.amount),
            "payment_method": payment.payment_method,
            "payment_status": payment.payment_status,
        }, status=201)

    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Invalid request data."},
            status=400
        )


@require_POST
@order_access("manage")
def update_payment_status(request, payment_id):
    try:
        data = json.loads(request.body)
        new_status = data.get("payment_status")

        valid_statuses = [
            "Pending",
            "Paid",
            "Failed",
            "Refunded"
        ]

        if new_status not in valid_statuses:
            return JsonResponse(
                {"error": "Invalid payment status."},
                status=400
            )

        payment = get_object_or_404(
            Payment,
            payment_id=payment_id
        )

        payment.payment_status = new_status
        payment.save(update_fields=["payment_status"])

        return JsonResponse({
            "message": "Payment status updated.",
            "payment_id": payment.payment_id,
            "payment_status": payment.payment_status,
        })

    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Invalid request data."},
            status=400
        )


@require_GET
@order_access("view")
def payment_details(request, order_id):
    payment = get_object_or_404(
        Payment,
        order__order_id=order_id
    )

    return JsonResponse({
        "payment_id": payment.payment_id,
        "order_id": payment.order.order_id,
        "amount": str(payment.amount),
        "payment_method": payment.payment_method,
        "payment_status": payment.payment_status,
        "payment_date": payment.payment_date.isoformat(),
    })


# =========================
# DELIVERY MANAGEMENT
# =========================

@require_POST
@order_access("manage")
def create_delivery(request, order_id):
    try:
        data = json.loads(request.body)

        order = get_object_or_404(
            FoodOrder,
            order_id=order_id
        )

        if order.status == "Cancelled":
            return JsonResponse(
                {"error": "Cannot create delivery for a cancelled order."},
                status=400
            )

        if Delivery.objects.filter(order=order).exists():
            return JsonResponse(
                {"error": "Delivery already exists for this order."},
                status=400
            )

        delivery = Delivery.objects.create(
            order=order,
            delivery_address=order.customer.address,
            courier_name=data.get("courier_name") or None,
            delivery_status="Pending"
        )

        return JsonResponse({
            "message": "Delivery created successfully.",
            "delivery_id": delivery.delivery_id,
            "order_id": order.order_id,
            "delivery_address": delivery.delivery_address,
            "courier_name": delivery.courier_name,
            "delivery_status": delivery.delivery_status,
        }, status=201)

    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Invalid request data."},
            status=400
        )


@require_POST
@order_access("manage")
def update_delivery_status(request, delivery_id):
    try:
        data = json.loads(request.body)
        new_status = data.get("delivery_status")

        valid_statuses = [
            "Pending",
            "Assigned",
            "Picked Up",
            "Delivered"
        ]

        if new_status not in valid_statuses:
            return JsonResponse(
                {"error": "Invalid delivery status."},
                status=400
            )

        delivery = get_object_or_404(
            Delivery,
            delivery_id=delivery_id
        )

        delivery.delivery_status = new_status

        if new_status == "Delivered":
            delivery.delivered_at = timezone.now()
            delivery.order.status = "Delivered"
            delivery.order.save(update_fields=["status"])

        delivery.save()

        return JsonResponse({
            "message": "Delivery status updated.",
            "delivery_id": delivery.delivery_id,
            "delivery_status": delivery.delivery_status,
        })

    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Invalid request data."},
            status=400
        )


@require_GET
@order_access("view")
def delivery_details(request, order_id):
    delivery = get_object_or_404(
        Delivery,
        order__order_id=order_id
    )

    return JsonResponse({
        "delivery_id": delivery.delivery_id,
        "order_id": delivery.order.order_id,
        "delivery_address": delivery.delivery_address,
        "courier_name": delivery.courier_name,
        "delivery_status": delivery.delivery_status,
        "created_at": delivery.created_at.isoformat(),
        "delivered_at": (
            delivery.delivered_at.isoformat()
            if delivery.delivered_at else None
        ),
    })
