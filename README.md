## Agentic Commerce Assignment — EvoAI

### 1) What is this project?

This is a tiny, fully deterministic “agent-like” system for an e-commerce brand. It can:

- Assist with products (search items, suggest sizes, estimate delivery time)
- Help with orders (find an order and enforce a strict 60-minute cancellation policy)
- Politely refuse off-policy requests (e.g., fake discount codes)

“Deterministic” means there is no external Large Language Model (LLM). All behavior is rule-based so that tests always produce the same output.

---

### 2) Repository layout

- `src/graph.py` — Orchestrates the flow (router, handlers, trace output)
- `src/tools.py` — Implements the “tools”: product search, size recommendation, ETA, order lookup, order cancellation
- `data/products.json` — Product catalog (mock data)
- `data/orders.json` — Orders (mock data)
- `prompts/system.md` — A brand voice/system prompt (not used by code, just context)
- `tests/run_tests.py` — Runs 4 example prompts through the agent and prints an internal JSON trace + final reply
- `README.md` — Quick setup and run instructions

---

### 3) How to run it

1. Install Python 3.10+.
2. In a terminal from the repo root:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Run the tests (which also act like demos):
   ```bash
   python -m tests.run_tests
   ```
You’ll see, for each test, a JSON “trace” (what the agent decided and which tools it used) and a final human-readable reply.

---

### 4) The data model (inputs the tools use)

The “tools” read from `data/products.json` and `data/orders.json`. These are plain JSON files so you can open them and inspect.

- `products.json` entries look like:
  ```json
  {
    "id": "P1001",
    "title": "Floral Midi Dress",
    "price": 89.0,
    "tags": ["wedding", "midi"],
    "sizes": ["S", "M", "L"],
    "color": "emerald"
  }
  ```
  Important fields:
  - `price` is a number, used to filter under a “cap”.
  - `tags` and `color` are used to match search queries.
  - `sizes` are used by the size recommender.

- `orders.json` entries look like:
  ```json
  {
    "order_id": "A1001",
    "email": "alex@example.com",
    "created_at": "2025-09-07T11:45:00Z",
    "items": [
      {"product_id": "P1001", "qty": 1}
    ]
  }
  ```
  Important fields:
  - `created_at` is an ISO-8601 UTC timestamp. It powers the 60-minute cancellation policy.

---

### 5) Orchestration: `src/graph.py`

This file contains the “agent” flow.

- `route(user_msg: str) -> str`
  - Classifies the user’s message into one of three intents:
    - `order_help` if it references orders/cancellation/email/order id
    - `product_assist` if it references shopping keywords (dress, midi, wedding, size, ETA)
    - `other` otherwise
  - It uses simple keyword checks for determinism.

- `handle_product_assist(user_msg: str) -> Trace`
  - Extracts:
    - An optional price cap (e.g., “under $120” → `price_cap = 120`)
    - Tags like `wedding` and `midi`
  - Calls tools in sequence:
    1) `product_search(query, price_max, tags)` → returns a list of matching products sorted by price
    2) Picks up to two results
    3) `size_recommender({ "between": "M/L", "available_sizes": [...] })` → suggests a size
    4) `eta(zip_code)` → extracts digits from the message and computes a delivery window
  - Builds a friendly response and a `Trace` JSON with:
    - `intent`
    - `tools_called` (which tools ran)
    - `evidence` (short product facts used)
    - `final_message` (what a user sees)

- `handle_order_help(user_msg: str, now_iso: Optional[str]) -> Trace`
  - Parses an `order_id` (e.g., `A1003`) and `email` from the message.
  - Calls `order_lookup(order_id, email)` → finds the order.
  - Enforces the 60-minute policy by calling `order_cancel(order_id, timestamp_iso=record["created_at"], now_iso=now_iso)`.
    - If within 60 minutes: cancellation is allowed.
    - Otherwise: it explains alternatives.
  - Returns a `Trace` with the policy decision and final message.

- `handle_other(user_msg: str) -> Trace`
  - Example guardrail: if a user asks for a non-existent discount code, politely refuses.

- `run_agent(user_msg: str, now_iso: Optional[str]) -> Tuple[str, str]`
  - Top-level entry point used by tests: returns `(trace_json, final_message)`.

---

### 6) The Tools: `src/tools.py`

Tools are plain Python functions. They load data, apply simple rules, and return dictionaries/lists. They are stateless and deterministic.

- Data loaders:
  - `_load_products()` and `_load_orders()` read JSON files into dataclass instances (`Product`, `Order`).

- `product_search(query, price_max, tags) -> List[Dict]`
  - Creates a lowercase “haystack” from `title + tags + color` and checks if any token from `query` appears.
  - Enforces `price_max` if provided and subset match for `tags`.
  - Sorts by `(price, title)` for determinism.

- `size_recommender(user_inputs) -> Dict`
  - If the user mentions they are “between M/L”, it prefers `M` when both `M` and `L` exist.
  - Otherwise defaults to `M` if present, else the first available size.

- `eta(zip_code) -> Dict`
  - Uses the first digit of the zip code to choose a shipping window:
    - Starts with 2–5 days for 5/6, 3–6 for 1–4, 4–7 default.

- `order_lookup(order_id, email) -> Optional[Dict]`
  - Exact match on both fields, returns order summary.

- `order_cancel(order_id, timestamp_iso, now_iso) -> Dict`
  - Enforces the 60-minute rule: `requested_at - created_at <= 3600` seconds.
  - `now_iso` is provided by tests to keep outputs deterministic.

---

### 7) Tests: `tests/run_tests.py`

The tests provide four scenarios and a fixed `NOW` timestamp. For each scenario, the script:

1. Calls `run_agent(prompt, now_iso=NOW)`
2. Prints the scenario name
3. Prints the internal JSON trace (so you can see decisions)
4. Prints the final reply string

Scenarios include product assistance, cancellation allowed within 60 minutes, cancellation blocked after 60 minutes, and a guardrail refusal.

---

### 8) Traces: Why they matter

Every handler returns a `Trace`. This is like an x-ray of the agent’s mind:

- Which intent was detected
- Which tools were called and in what order
- What minimal evidence the final answer used
- What the final message says

Because the project is deterministic, traces are perfect for debugging and for writing acceptance tests.

---

### 9) Extending the project (learning exercises)

Try these incremental exercises to deepen your understanding:

1. Product search improvements
   - Add filtering by `color`
   - Add sorting by relevance (token overlap count)

2. Size recommender
   - Add rules for being between other sizes (e.g., `S/M`, `L/XL`)
   - Incorporate height or chest measurements if present in the message

3. ETA tool
   - Use the first two digits of the zip for more granular windows
   - Add a “weekend delay” rule

4. Orders
   - Add a “return within 30 days” acceptance rule
   - Add address edit within 12 hours of order creation

5. Router
   - Replace keyword routing with a tiny intent classifier (still deterministic)

---

### 10) Troubleshooting

- "Module not found" when running tests
  - Ensure you’re running from repo root: `python -m tests.run_tests`
  - Activate your virtual environment: `source .venv/bin/activate`

- JSON decode error
  - Check that `data/products.json` and `data/orders.json` are valid JSON.

- Timezone issues with cancellation
  - Keep times in UTC ISO (with trailing `Z`). The code already normalizes to UTC.

---

### 11) Key takeaways

- Deterministic agents are predictable and testable.
- Separating orchestration (`graph.py`) from tools (`tools.py`) keeps logic clean.
- JSON traces expose the full reasoning chain for auditability.

Take your time reading the code alongside this guide. Make small changes and rerun `python -m tests.run_tests` to see how your edits affect behavior.


