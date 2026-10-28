"""sales_query: a structured, read-only view of the sales table.

The model does not write SQL. It picks a metric, a grouping and filters; the
backend builds the query. That is the least-access rule from Lesson 5 applied
to an agent: the tool cannot drop, update or read anything but sales.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from ..db import Sale

METRICS = {"revenue", "items", "orders", "avg_order"}
GROUP_BY = {"none", "product", "category", "branch", "channel", "day", "week", "month", "payment_method", "customer_type"}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def sales_query(db: Session, *, metric: str = "revenue", group_by: str = "none", date_from: str | None = None,
                date_to: str | None = None, branch: str | None = None, product: str | None = None,
                category: str | None = None, include_refunded: bool = False, top_n: int = 10) -> dict:
    if metric not in METRICS:
        return {"error": f"unknown metric '{metric}'", "allowed": sorted(METRICS)}
    if group_by not in GROUP_BY:
        return {"error": f"unknown group_by '{group_by}'", "allowed": sorted(GROUP_BY)}
    top_n = max(1, min(int(top_n or 10), 50))

    try:
        d_from, d_to = _parse_date(date_from), _parse_date(date_to)
    except ValueError:
        return {"error": "dates must be YYYY-MM-DD"}

    revenue = func.sum(Sale.line_total)
    items = func.sum(Sale.quantity)
    orders = func.count(func.distinct(Sale.order_id))
    metric_expr = {"revenue": revenue, "items": items, "orders": orders, "avg_order": revenue / func.nullif(orders, 0)}[metric]

    group_expr = None
    if group_by == "day":
        group_expr = Sale.order_date
    elif group_by == "week":
        # ISO-ish week bucket that works on SQLite and Postgres: first day of the week as a date string.
        group_expr = func.strftime("%Y-W%W", Sale.order_date) if db.bind.dialect.name == "sqlite" else func.to_char(Sale.order_date, "IYYY-\"W\"IW")
    elif group_by == "month":
        group_expr = func.strftime("%Y-%m", Sale.order_date) if db.bind.dialect.name == "sqlite" else func.to_char(Sale.order_date, "YYYY-MM")
    elif group_by != "none":
        group_expr = getattr(Sale, group_by)

    where = []
    if not include_refunded:
        where.append(Sale.status == "completed")
    if d_from:
        where.append(Sale.order_date >= d_from)
    if d_to:
        where.append(Sale.order_date <= d_to)
    if branch:
        where.append(func.lower(Sale.branch).like(f"%{branch.lower()}%"))
    if product:
        where.append(func.lower(Sale.product).like(f"%{product.lower()}%"))
    if category:
        where.append(func.lower(Sale.category).like(f"%{category.lower()}%"))

    if group_expr is None:
        stmt = select(metric_expr.label("value"), revenue.label("revenue"), items.label("items"), orders.label("orders")).where(*where)
        row = db.execute(stmt).one()
        return {
            "metric": metric, "group_by": "none", "filters": _filters(d_from, d_to, branch, product, category, include_refunded),
            "value": _num(row.value), "revenue": _num(row.revenue), "items": int(row.items or 0), "orders": int(row.orders or 0),
        }

    stmt = (select(group_expr.label("key"), metric_expr.label("value"), revenue.label("revenue"), items.label("items"), orders.label("orders"))
            .where(*where).group_by(group_expr))
    stmt = stmt.order_by(group_expr) if group_by in {"day", "week", "month"} else stmt.order_by(metric_expr.desc())
    stmt = stmt.limit(top_n if group_by not in {"day", "week", "month"} else 400)
    rows = [{"key": str(r.key), "value": _num(r.value), "revenue": _num(r.revenue), "items": int(r.items or 0), "orders": int(r.orders or 0)}
            for r in db.execute(stmt)]
    return {"metric": metric, "group_by": group_by, "filters": _filters(d_from, d_to, branch, product, category, include_refunded),
            "rows": rows, "row_count": len(rows)}


def data_range(db: Session) -> tuple[date | None, date | None]:
    return db.execute(select(func.min(Sale.order_date), func.max(Sale.order_date))).one()


def _filters(d_from, d_to, branch, product, category, include_refunded) -> dict:
    return {"date_from": str(d_from) if d_from else None, "date_to": str(d_to) if d_to else None,
            "branch": branch, "product": product, "category": category, "include_refunded": include_refunded}


def _num(v) -> float:
    return round(float(v or 0), 2)
