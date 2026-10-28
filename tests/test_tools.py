"""Unit tests: the deterministic parts. Same input, same output, every time."""
import pytest

from app.tools.invoices import log_invoice, lookup_supplier, parse_amount
from app.tools.sales import sales_query


@pytest.mark.parametrize("raw,expected", [
    ("₪1,240.00", 1240.0), ("1 240", 1240.0), ("NIS 85", 85.0), (1240, 1240.0), (99.5, 99.5),
    ("TBD", None), ("", None), (None, None), ("-20", None), ("call us", None),
])
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


def test_log_invoice_same_source_ref_is_one_row(client, db):
    first = log_invoice(db, supplier="Levi Flour", invoice_number="A-1", amount=1240, source_ref="img_t1")
    second = log_invoice(db, supplier="Levi Flour", invoice_number="A-1", amount=1240, source_ref="img_t1")
    assert first["created"] is True
    assert second["created"] is False and second["reason"] == "duplicate"
    assert second["id"] == first["id"]


def test_log_invoice_same_supplier_and_number_is_one_row(client, db):
    a = log_invoice(db, supplier="Golan Dairy", invoice_number="7781", amount=500, source_ref="img_t2a")
    b = log_invoice(db, supplier="golan dairy", invoice_number="7781", amount=500, source_ref="img_t2b")
    assert b["created"] is False and b["id"] == a["id"]


def test_unreadable_amount_goes_to_needs_a_look(client, db):
    row = log_invoice(db, supplier="Negev Eggs", invoice_number="9", amount=None, source_ref="img_t3")
    assert row["status"] == "needs_a_look"
    assert row["amount"] is None
    assert "amount unreadable" in (row["notes"] or "")


def test_large_amount_is_flagged_not_blocked(client, db):
    row = log_invoice(db, supplier="Big Oven Ltd", invoice_number="X1", amount="₪6,200", source_ref="img_t4")
    assert row["status"] == "logged" and row["flagged"] is True and row["amount"] == 6200.0


def test_lookup_supplier_partial_match(client, db):
    res = lookup_supplier(db, name="vanilla")
    assert res["known_supplier"] is True
    assert any("Vanilla" in m["supplier"] for m in res["matches"])
    assert lookup_supplier(db, name="nobody-here")["known_supplier"] is False


def test_sales_query_totals_match_the_dataset(client, db):
    # The Lesson 4/5 dataset: completed revenue ₪647,065 · 40,194 items · 14,196 completed orders
    # (14,421 orders in total once refunded lines are included).
    res = sales_query(db, metric="revenue", group_by="none")
    assert round(res["revenue"]) == 647065
    assert res["items"] == 40194
    assert res["orders"] == 14196
    everything = sales_query(db, metric="orders", group_by="none", include_refunded=True)
    assert everything["orders"] == 14421


def test_branch_names_are_cleaned_at_the_door(client, db):
    # The CSV has "Herzliya " with a trailing space; the seed strips it, so there are exactly four branches.
    res = sales_query(db, metric="revenue", group_by="branch", include_refunded=True)
    assert res["row_count"] == 4
    assert sorted(r["key"] for r in res["rows"]) == ["Herzliya", "Ramat Gan", "Tel Aviv - Dizengoff", "Tel Aviv - Florentin"]


def test_sales_query_ranking_and_filters(client, db):
    top = sales_query(db, metric="items", group_by="product", top_n=3)
    assert top["row_count"] == 3
    assert top["rows"][0]["value"] >= top["rows"][1]["value"] >= top["rows"][2]["value"]
    month = sales_query(db, metric="revenue", group_by="branch", date_from="2026-08-01", date_to="2026-08-31")
    assert 0 < month["row_count"] <= 4
    assert sales_query(db, metric="nope", group_by="none")["error"].startswith("unknown metric")
    assert sales_query(db, metric="revenue", group_by="none", date_from="31/08/2026")["error"] == "dates must be YYYY-MM-DD"
