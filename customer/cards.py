from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from accounts.models import SavedCard

SELECTED_CARD_KEY = "checkout_card_id"


@login_required
@require_POST
def select_card(request):
    card_id = request.POST.get("card_id", "")
    if not card_id.isascii() or not card_id.isdecimal() or len(card_id) > 18:
        return JsonResponse({"error": "Invalid card."}, status=400)
    card = get_object_or_404(SavedCard, user=request.user, pk=card_id)
    request.session[SELECTED_CARD_KEY] = card.pk
    return JsonResponse({"card_id": card.pk, "label": str(card)})
