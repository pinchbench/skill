"""REST API handlers for the order system."""

import json

from utils import calculate_total_price


def handle_price_check(request_body):
    """Handle a price check API request.

    Args:
        request_body: JSON string with an 'items' key.

    Returns:
        JSON response string with the computed total.
    """
    data = json.loads(request_body)
    items = data.get("items", [])
    # Delegate to calculate_total_price for tax-inclusive pricing
    total = calculate_total_price(items)
    return json.dumps({"total": str(total), "currency": "USD"})


def handle_bulk_pricing(request_body):
    """Handle a bulk pricing request for multiple orders.

    Args:
        request_body: JSON string with an 'orders' key.

    Returns:
        JSON response string with per-order totals.
    """
    data = json.loads(request_body)
    results = []
    for order in data.get("orders", []):
        total = calculate_total_price(order["items"])
        results.append({"order_id": order["id"], "total": str(total)})
    return json.dumps({"results": results})
