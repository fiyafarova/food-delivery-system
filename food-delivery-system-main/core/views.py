import json
from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from django.db import transaction
from django.db.models import Sum, F, DecimalField, ExpressionWrapper

from .models import Customer, Food_Item, Food_Order, Order_Item


# =========================
# SHOPPING CART
# =========================

def get_cart(request):
    return request.session.get("cart", {})


@require_GET
def view_cart(request):
    cart = get_cart(request)
    items = []
    total = Decimal("0.00")

    for food_id, quantity in cart.items():
        food = Food_Item.objects.filter(
            food_item_id=food_id,
            is_available=True
        ).first()

        if food:
            subtotal = food.price * quantity
            total += subtotal

            items.append({
                "food_item_id": food.food_item_id,
                "name": food.name,
                "price": str(food.price),
                "quantity": quantity,
                "subtotal": str(subtotal),
            })

    return JsonResponse({
        "items": items,
        "total": str(total),
    })


@require_POST
def add_to_cart(request):
    try:
        data = json.loads(request.body)
        food_id = int(data.get("food_item_id"))
        quantity = int(data.get("quantity", 1))

        if quantity <= 0:
            return JsonResponse(
                {"error": "Quantity must be greater than zero."},
                status=400
            )

        food = get_object_or_404(
            Food_Item,
            food_item_id=food_id,
            is_available=True
        )

        cart = get_cart(request)
        current_quantity = cart.get(str(food_id), 0)
        cart[str(food_id)] = current_quantity + quantity

        request.session["cart"] = cart
        request.session.modified = True

        return JsonResponse({
            "message": "Item added to cart.",
            "food_item": food.name,
            "quantity": cart[str(food_id)],
        })

    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid request data."}, status=400)


@require_POST
def update_cart(request):
    try:
        data = json.loads(request.body)
        food_id = str(int(data.get("food_item_id")))
        quantity = int(data.get("quantity"))

        if quantity <= 0:
            return JsonResponse(
                {"error": "Quantity must be greater than zero."},
                status=400
            )

        cart = get_cart(request)

        if food_id not in cart:
            return JsonResponse(
                {"error": "Item is not in the cart."},
                status=404
            )

        cart[food_id] = quantity
        request.session["cart"] = cart
        request.session.modified = True

        return JsonResponse({"message": "Cart updated."})

    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid request data."}, status=400)


@require_POST
def remove_from_cart(request):
    try:
        data = json.loads(request.body)
        food_id = str(int(data.get("food_item_id")))

        cart = get_cart(request)

        if food_id not in cart:
            return JsonResponse(
                {"error": "Item is not in the cart."},
                status=404
            )

        del cart[food_id]

        request.session["cart"] = cart
        request.session.modified = True

        return JsonResponse({"message": "Item removed from cart."})

    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid request data."}, status=400)


# =========================
# CREATE ORDER
# =========================

@require_POST
def create_order(request):
    try:
        data = json.loads(request.body)
        customer_id = int(data.get("customer_id"))
        cart = get_cart(request)

        if not cart:
            return JsonResponse(
                {"error": "Your cart is empty."},
                status=400
            )

        customer = get_object_or_404(
            Customer,
            customer_id=customer_id
        )

        with transaction.atomic():
            order = Food_Order.objects.create(
                customer=customer,
                status="Placed",
                total_amount=Decimal("0.00")
            )

            total = Decimal("0.00")

            for food_id, quantity in cart.items():
                food = get_object_or_404(
                    Food_Item,
                    food_item_id=int(food_id),
                    is_available=True
                )

                quantity = int(quantity)

                if quantity <= 0:
                    raise ValueError("Invalid quantity.")

                unit_price = food.price
                total += unit_price * quantity

                Order_Item.objects.create(
                    order=order,
                    food_item=food,
                    quantity=quantity,
                    unit_price=unit_price
                )

            order.total_amount = total
            order.save(update_fields=["total_amount"])

        request.session["cart"] = {}
        request.session.modified = True

        return JsonResponse({
            "message": "Order created successfully.",
            "order_id": order.order_id,
            "status": order.status,
            "total_amount": str(order.total_amount),
        }, status=201)

    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid order data."}, status=400)


# =========================
# ORDER DETAILS
# =========================

@require_GET
def order_details(request, order_id):
    order = get_object_or_404(
        Food_Order,
        order_id=order_id
    )

    items = []

    for item in order.items.all():
        items.append({
            "food_item_id": item.food_item.food_item_id,
            "food_name": item.food_item.name,
            "quantity": item.quantity,
            "unit_price": str(item.unit_price),
            "subtotal": str(item.unit_price * item.quantity),
        })

    return JsonResponse({
        "order_id": order.order_id,
        "customer_id": order.customer.customer_id,
        "order_date": order.order_date.isoformat(),
        "status": order.status,
        "total_amount": str(order.total_amount),
        "items": items,
    })


# =========================
# ORDER STATUS
# =========================

@require_POST
def update_order_status(request, order_id):
    try:
        data = json.loads(request.body)
        new_status = data.get("status")

        valid_statuses = [
            "Placed",
            "Preparing",
            "Delivered",
            "Cancelled"
        ]

        if new_status not in valid_statuses:
            return JsonResponse(
                {"error": "Invalid order status."},
                status=400
            )

        order = get_object_or_404(
            Food_Order,
            order_id=order_id
        )

        order.status = new_status
        order.save(update_fields=["status"])

        return JsonResponse({
            "message": "Order status updated.",
            "order_id": order.order_id,
            "status": order.status,
        })

    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid request data."}, status=400)


# =========================
# ORDER HISTORY
# =========================

@require_GET
def order_history(request, customer_id):
    customer = get_object_or_404(
        Customer,
        customer_id=customer_id
    )

    orders = Food_Order.objects.filter(
        customer=customer
    ).order_by("-order_date")

    result = []

    for order in orders:
        result.append({
            "order_id": order.order_id,
            "order_date": order.order_date.isoformat(),
            "status": order.status,
            "total_amount": str(order.total_amount),
            "items_count": order.items.count(),
        })

    return JsonResponse({
        "customer_id": customer.customer_id,
        "orders": result,
    })
from django.utils import timezone
from .models import Payment, Delivery


# =========================
# PAYMENT MANAGEMENT
# =========================

@require_POST
def create_payment(request, order_id):
    try:
        data = json.loads(request.body)

        order = get_object_or_404(
            Food_Order,
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
def create_delivery(request, order_id):
    try:
        data = json.loads(request.body)

        order = get_object_or_404(
            Food_Order,
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
