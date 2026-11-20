
TRANSITIONS = {
    "Placed": ["Preparing", "Cancelled"],
    "Preparing": ["Delivered", "Cancelled"],
    "Delivered": [],
    "Cancelled": [],
}

STATUSES = list(TRANSITIONS.keys())
