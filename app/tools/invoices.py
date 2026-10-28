"""log_invoice and lookup_supplier: the two writes-and-reads around invoices.

Rules from spec.md, enforced here and not in the prompt:
- the same invoice twice makes one row (source_ref, or supplier + number);
- an unreadable amount is never guessed: the row goes to "needs_a_look";
- anything over the threshold is flagged, never acted on.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import Invoice, Supplier

FLAG_THRESHOLD = 5000.0  # spec.md §6
_AMOUNT_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def parse_amount(text: str | float | int | None) -> float | None:
    """'₪1,240.00' -> 1240.0; '1 240' -> 1240.0; 'TBD' -> None; negatives -> None."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text) if text > 0 else None
    cleaned = str(text).replace("₪", "").replace("NIS", "").replace("ILS", "").replace(" ", "")
    m = _AMOUNT_RE.search(cleaned)
    if not m:
        return None
    try:
        value = float(m.group(0).replace(",", ""))
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def log_invoice(db: Session, *, supplier: str | None, invoice_number: str | None = None, amount=None,
                currency: str = "ILS", invoice_date: str | None = None, source_ref: str | None = None,
                notes: str | None = None, logged_by: int | None = None) -> dict:
    supplier = (supplier or "").strip()
    invoice_number = (invoice_number or "").strip() or None
    source_ref = (source_ref or "").strip() or None
    amount_value = parse_amount(amount)

    # Idempotency: the same invoice twice is one row (Lesson 5, run-it-twice).
    existing = None
    if source_ref:
        existing = db.scalar(select(Invoice).where(Invoice.source_ref == source_ref))
    if existing is None and supplier and invoice_number:
        existing = db.scalar(select(Invoice).where(func.lower(Invoice.supplier) == supplier.lower(),
                                                   Invoice.invoice_number == invoice_number))
    if existing is not None:
        return {"created": False, "reason": "duplicate", **_row(existing)}

    problems = []
    if not supplier:
        problems.append("supplier missing")
    if amount_value is None:
        problems.append("amount unreadable")
    status = "needs_a_look" if problems else "logged"
    flagged = bool(amount_value and amount_value > FLAG_THRESHOLD)

    inv = Invoice(
        supplier=supplier or "unknown", invoice_number=invoice_number, amount=amount_value,
        currency=(currency or "ILS").upper()[:3], invoice_date=_parse_date(invoice_date), status=status,
        flagged=flagged, source_ref=source_ref,
        notes="; ".join(filter(None, [notes, *problems])) or None, logged_by=logged_by,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return {"created": True, "reason": None, **_row(inv)}


def lookup_supplier(db: Session, *, name: str) -> dict:
    needle = (name or "").strip().lower()
    if not needle:
        return {"matches": []}
    rows = db.scalars(select(Supplier).where(func.lower(Supplier.name).like(f"%{needle}%"))).all()
    if not rows:
        # second chance: any word of the name
        for word in [w for w in re.split(r"\W+", needle) if len(w) > 3]:
            rows = db.scalars(select(Supplier).where(func.lower(Supplier.name).like(f"%{word}%"))).all()
            if rows:
                break
    by_name: dict[str, dict] = {}
    for r in rows:
        entry = by_name.setdefault(r.name, {"supplier": r.name, "items": []})
        entry["items"].append({"item": r.item, "unit": r.unit, "price": r.price, "currency": r.currency})
    return {"matches": list(by_name.values()), "known_supplier": bool(by_name)}


def recent_invoices(db: Session, limit: int = 50) -> list[dict]:
    rows = db.scalars(select(Invoice).order_by(Invoice.created_at.desc()).limit(limit)).all()
    return [_row(r) for r in rows]


def _row(inv: Invoice) -> dict:
    return {
        "id": inv.id, "supplier": inv.supplier, "invoice_number": inv.invoice_number, "amount": inv.amount,
        "currency": inv.currency, "invoice_date": str(inv.invoice_date) if inv.invoice_date else None,
        "status": inv.status, "flagged": inv.flagged, "source_ref": inv.source_ref, "notes": inv.notes,
        "created_at": inv.created_at.isoformat(timespec="seconds") if inv.created_at else None,
    }
