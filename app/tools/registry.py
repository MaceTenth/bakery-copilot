"""Tool definitions the model sees, and the dispatcher that runs them."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from . import invoices, sales

TOOLS: list[dict[str, Any]] = [
    {
        "name": "sales_query",
        "description": (
            "Read-only query over the bakery's sales lines (one row per product per order). "
            "Use it for any question about revenue, items sold, order counts, best sellers, branches, "
            "channels or trends. Pick a metric and a grouping; filter by date range (YYYY-MM-DD), branch, "
            "product or category. Refunded lines are excluded unless include_refunded is true. "
            "Never guess numbers: if the answer needs data, call this tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "enum": sorted(sales.METRICS), "description": "revenue (ILS), items (units), orders (distinct orders) or avg_order (revenue per order)."},
                "group_by": {"type": "string", "enum": sorted(sales.GROUP_BY), "description": "none for a single total; product/branch/... for a ranking; day/week/month for a trend."},
                "date_from": {"type": "string", "description": "inclusive start date YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "inclusive end date YYYY-MM-DD"},
                "branch": {"type": "string", "description": "substring match on branch name"},
                "product": {"type": "string", "description": "substring match on product name"},
                "category": {"type": "string", "description": "substring match on category (Bread, Pastry, Drinks, Sweet, ...)"},
                "include_refunded": {"type": "boolean", "default": False},
                "top_n": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            },
            "required": ["metric", "group_by"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lookup_supplier",
        "description": "Look up a supplier by (partial) name in the bakery's supplier list. Returns the canonical name and the items and usual prices we buy from them. Call it before logging an invoice to normalise the supplier name.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "supplier name as written on the invoice"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "log_invoice",
        "description": (
            "Record one supplier invoice as one row. Pass the fields exactly as read from the document; "
            "pass amount as null if you cannot read it with confidence, and the row will be marked needs_a_look. "
            "Always pass source_ref (the image reference given in the message) so the same invoice is never logged twice. "
            "Never call this to modify or delete an existing row."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier": {"type": "string"},
                "invoice_number": {"type": ["string", "null"]},
                "amount": {"type": ["number", "null"], "description": "total amount, numbers only; null if unreadable"},
                "currency": {"type": "string", "default": "ILS"},
                "invoice_date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
                "source_ref": {"type": ["string", "null"], "description": "the image reference from the message, e.g. img_8f3a2c"},
                "notes": {"type": ["string", "null"]},
            },
            "required": ["supplier", "amount"],
            "additionalProperties": False,
        },
    },
]

TOOL_NAMES = {t["name"] for t in TOOLS}
MAX_RESULT_CHARS = 12000


def execute(name: str, tool_input: dict[str, Any], db: Session, *, user_id: int | None = None) -> str:
    """Run one tool and return its result as a JSON string for the model."""
    try:
        if name == "sales_query":
            result = sales.sales_query(db, **_clean(tool_input))
        elif name == "lookup_supplier":
            result = invoices.lookup_supplier(db, name=str(tool_input.get("name", "")))
        elif name == "log_invoice":
            result = invoices.log_invoice(db, logged_by=user_id, **_clean(tool_input))
        else:
            result = {"error": f"unknown tool '{name}'"}
    except Exception as exc:  # the loop must survive a bad input; the model sees the error
        result = {"error": f"{type(exc).__name__}: {exc}"}
    text = json.dumps(result, ensure_ascii=False, default=str)
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + '... (truncated)"}'
    return text


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}
