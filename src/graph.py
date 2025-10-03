from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

from .tools import product_search, size_recommender, eta, order_lookup, order_cancel

@dataclass
class Trace:
    intent: str
    tools_called: List[str]
    evidence: List[Dict[str, Any]]
    policy_decision: Optional[Dict[str, Any]]
    final_message: str

    def to_json(self) -> str:
        return json.dumps({
            "intent": self.intent,
            "tools_called": self.tools_called,
            "evidence": self.evidence,
            "policy_decision": self.policy_decision,
            "final_message": self.final_message,
        }, ensure_ascii=False)

# Router

def route(user_msg: str) -> str:
    m = user_msg.lower()
    if any(k in m for k in ["order", "cancel", "order id", "email@"]) or ("cancel" in m and "order" in m):
        return "order_help"
    if any(k in m for k in ["dress", "midi", "wedding", "size", "eta", "zip", "between"]):
        return "product_assist"
    return "other"

# ToolSelector + flow

def handle_product_assist(user_msg: str) -> Trace:
    # Parse simple fields deterministically
    price_cap = None
    tags: List[str] = []
    query = user_msg
    # Extract price like "$120" or "under 120"
    for token in user_msg.replace("$", " ").replace("—", " ").split():
        t = token.strip().lower().strip(".,?")
        if t.isdigit():
            price_cap = float(t)
            break
    if "under" in user_msg.lower() and price_cap is None:
        price_cap = 120.0
    if "wedding" in user_msg.lower():
        tags.append("wedding")
    if "midi" in user_msg.lower():
        tags.append("midi")

    tools_used: List[str] = []

    products = product_search(query=query, price_max=price_cap, tags=tags or None)
    tools_used.append("product_search")

    # Choose up to 2 items under cap
    picks = products[:2]

    size_inputs = {
        "between": "M/L" if "between" in user_msg.lower() else "",
        "available_sizes": list({s for p in picks for s in p.get("sizes", [])}),
    }
    size_advice = size_recommender(size_inputs)
    tools_used.append("size_recommender")

    # Extract zip (simple digits longest chunk)
    zip_digits = "".join([c for c in user_msg if c.isdigit()])
    if len(zip_digits) >= 5:
        zip_code = zip_digits[:6]  # support 560001
    else:
        zip_code = zip_digits
    eta_window = eta(zip_code)
    tools_used.append("eta")

    evidence = []
    for p in picks:
        evidence.append({
            "product_id": p["id"],
            "title": p["title"],
            "price": p["price"],
            "sizes": p["sizes"],
        })

    # Compose final message
    if not picks:
        msg = "I couldn’t find items under your price cap. Want me to widen the search?"
    else:
        lines = []
        for p in picks:
            sizes = "/".join(p.get("sizes", []))
            lines.append(f"- {p['title']} — ${p['price']} — sizes {sizes}")
        size_line = f"Size tip: go {size_advice['recommended']} — {size_advice['rationale']}" if size_advice.get("recommended") else "Size tip: share height/chest if you'd like a finer fit."
        eta_line = f"ETA to {zip_code}: {eta_window['days_min']}–{eta_window['days_max']} days"
        msg = "Here are two options under your cap:\n" + "\n".join(lines) + f"\n{size_line}\n{eta_line}"

    trace = Trace(
        intent="product_assist",
        tools_called=tools_used,
        evidence=evidence,
        policy_decision=None,
        final_message=msg,
    )
    return trace


def handle_order_help(user_msg: str, now_iso: Optional[str] = None) -> Trace:
    # naive parse of order_id and email
    tokens = user_msg.replace("—", " ").replace("-", " ").split()
    order_id = None
    email = None
    for t in tokens:
        if "@" in t:
            email = t.strip().strip(".")
        if t.upper().startswith("A") and t[1:].isdigit():
            order_id = t.strip().strip(".")
    tools_used: List[str] = []
    evidence: List[Dict[str, Any]] = []

    if not order_id or not email:
        msg = "To help with orders, please provide both order_id and email."
        return Trace("order_help", tools_used, evidence, None, msg)

    record = order_lookup(order_id, email)
    tools_used.append("order_lookup")

    if not record:
        msg = "I couldn’t find that order. Please check the order_id and email."
        return Trace("order_help", tools_used, evidence, None, msg)

    evidence.append({
        "order_id": record["order_id"],
        "email": record["email"],
        "created_at": record["created_at"],
    })

    # PolicyGuard: 60-minute rule
    cancel_result = order_cancel(order_id, timestamp_iso=record["created_at"], now_iso=now_iso)
    tools_used.append("order_cancel")

    if cancel_result["cancelled"]:
        policy = {"cancel_allowed": True}
        msg = f"Cancellation complete for {order_id}. A confirmation email will follow."
    else:
        policy = {"cancel_allowed": False, "reason": ">60 min"}
        msg = (
            "I can’t cancel as it’s past 60 minutes since creation. "
            "Options: edit shipping address, offer store credit after delivery, or I can hand off to support."
        )

    return Trace(
        intent="order_help",
        tools_called=tools_used,
        evidence=evidence,
        policy_decision=policy,
        final_message=msg,
    )


def handle_other(user_msg: str) -> Trace:
    m = user_msg.lower()
    if "discount" in m and ("code" in m or "coupon" in m):
        trace = Trace(
            intent="other",
            tools_called=[],
            evidence=[],
            policy_decision={"refuse": True},
            final_message=(
                "I can’t provide a non-existent discount code. You can join our newsletter or check first-order perks."
            ),
        )
        return trace
    return Trace("other", [], [], None, "I can help with products or orders. How can I help?")


def run_agent(user_msg: str, now_iso: Optional[str] = None) -> Tuple[str, str]:
    intent = route(user_msg)
    if intent == "product_assist":
        trace = handle_product_assist(user_msg)
    elif intent == "order_help":
        trace = handle_order_help(user_msg, now_iso=now_iso)
    else:
        trace = handle_other(user_msg)
    return trace.to_json(), trace.final_message
