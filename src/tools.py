from __future__ import annotations
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PRODUCTS_PATH = os.path.join(DATA_DIR, "products.json")
ORDERS_PATH = os.path.join(DATA_DIR, "orders.json")

@dataclass
class Product:
    id: str
    title: str
    price: float
    tags: List[str]
    sizes: List[str]
    color: str

@dataclass
class Order:
    order_id: str
    email: str
    created_at: str
    items: List[Dict[str, Any]]

# Utilities

def _load_products() -> List[Product]:
    with open(PRODUCTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Product(**p) for p in data]


def _load_orders() -> List[Order]:
    with open(ORDERS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Order(**o) for o in data]


# Tools

def product_search(query: str, price_max: Optional[float], tags: Optional[List[str]]) -> List[Dict[str, Any]]:
    products = _load_products()
    q = (query or "").lower()
    tagset = set((tags or []))
    results: List[Product] = []
    for p in products:
        if price_max is not None and p.price > price_max:
            continue
        hay = f"{p.title} {' '.join(p.tags)} {p.color}".lower()
        if q and not any(token in hay for token in q.split()):
            continue
        if tagset and not tagset.issubset(set(p.tags)):
            continue
        results.append(p)
    # sort by price asc for determinism
    results.sort(key=lambda x: (x.price, x.title))
    return [p.__dict__ for p in results]


def size_recommender(user_inputs: Dict[str, Any]) -> Dict[str, Any]:
    # Simple heuristic: if between M/L, prefer M when sizes include M and L both; otherwise choose available.
    stated_between = str(user_inputs.get("between", "")).upper()
    available_sizes = [s.upper() for s in user_inputs.get("available_sizes", [])]
    recommendation = {
        "recommended": None,
        "rationale": "",
    }
    if stated_between == "M/L":
        if "M" in available_sizes and "L" in available_sizes:
            recommendation["recommended"] = "M"
            recommendation["rationale"] = "Between M/L; our cut runs true to size, so M fits most."
            return recommendation
        elif "M" in available_sizes:
            recommendation["recommended"] = "M"
            recommendation["rationale"] = "Between M/L; L unavailable here."
            return recommendation
        elif "L" in available_sizes:
            recommendation["recommended"] = "L"
            recommendation["rationale"] = "Between M/L; M unavailable here."
            return recommendation
    # Fallback: first available size or M if present
    if "M" in available_sizes:
        recommendation["recommended"] = "M"
        recommendation["rationale"] = "Default to M when unsure."
    elif available_sizes:
        recommendation["recommended"] = available_sizes[0]
        recommendation["rationale"] = "Select first available size."
    else:
        recommendation["recommended"] = None
        recommendation["rationale"] = "No sizes available."
    return recommendation


def eta(zip_code: str) -> Dict[str, Any]:
    # Rule-based ETA windows by leading digit; deterministic.
    zip_str = str(zip_code)
    if not zip_str or not zip_str[0].isdigit():
        return {"days_min": 4, "days_max": 7}
    lead = int(zip_str[0])
    if lead in (5, 6):
        return {"days_min": 2, "days_max": 5}
    if lead in (1, 2, 3, 4):
        return {"days_min": 3, "days_max": 6}
    return {"days_min": 4, "days_max": 7}


def order_lookup(order_id: str, email: str) -> Optional[Dict[str, Any]]:
    orders = _load_orders()
    for o in orders:
        if o.order_id == order_id and o.email.lower() == email.lower():
            return {
                "order_id": o.order_id,
                "email": o.email,
                "created_at": o.created_at,
                "items": o.items,
            }
    return None


def order_cancel(order_id: str, timestamp_iso: str, now_iso: Optional[str] = None) -> Dict[str, Any]:
    # Enforce 60-minute rule strictly, using passed now for determinism in tests.
    orders = _load_orders()
    target: Optional[Order] = None
    for o in orders:
        if o.order_id == order_id:
            target = o
            break
    if target is None:
        return {"cancelled": False, "reason": "order_not_found"}

    created_at = datetime.fromisoformat(target.created_at.replace("Z", "+00:00"))
    requested_at = datetime.fromisoformat((now_iso or timestamp_iso).replace("Z", "+00:00"))
    delta = requested_at - created_at
    within_60 = delta.total_seconds() <= 60 * 60
    return {
        "cancelled": within_60,
        "reason": None if within_60 else ">60_minute_window",
        "created_at": target.created_at,
        "requested_at": requested_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
