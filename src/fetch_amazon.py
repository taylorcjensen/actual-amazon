#!/usr/bin/env python3
import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from amazonorders.conf import AmazonOrdersConfig
from amazonorders.orders import AmazonOrders
from amazonorders.session import AmazonSession
from amazonorders.transactions import AmazonTransactions


def main() -> None:
    args = parse_args()
    config = AmazonOrdersConfig(data={
        "order_class": "amazon_order.RecoverableOrder",
        "selectors_class": "amazon_order.AmazonSelectors",
    })
    session = AmazonSession(domain=args.domain, debug=args.debug, config=config)
    session.login()

    orders_client = AmazonOrders(session)
    orders = fetch_order_history(orders_client, args)

    transactions_client = AmazonTransactions(session)
    transactions = transactions_client.get_transactions(days=get_transaction_days(args))

    if args.supplement_missing_orders:
        orders.extend(fetch_missing_transaction_orders(orders_client, orders, transactions, args.supplement_after))

    payload = {
        "orders": [to_plain_value(order) for order in orders],
        "transactions": [to_plain_value(transaction) for transaction in transactions],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
    print(f"Wrote {args.output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Amazon orders and transactions as JSON.")
    parser.add_argument("--output", type=Path, default=Path("data/amazon-history.json"))
    parser.add_argument("--year", type=int)
    parser.add_argument("--time-filter", choices=["last30", "months-3"])
    parser.add_argument("--transaction-days", type=int, default=365)
    parser.add_argument("--start-date", help="Earliest transaction date to fetch, YYYY-MM-DD. Overrides --transaction-days and fetches all needed order years.")
    parser.add_argument("--domain", default="amazon.com")
    parser.add_argument("--full-details", action="store_true", default=True)
    parser.add_argument("--supplement-missing-orders", action="store_true", default=True)
    parser.add_argument("--no-supplement-missing-orders", action="store_false", dest="supplement_missing_orders")
    parser.add_argument("--supplement-after")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def fetch_order_history(orders_client: AmazonOrders, args: argparse.Namespace) -> list[Any]:
    if args.time_filter:
        return orders_client.get_orders(
            full_details=args.full_details,
            time_filter=args.time_filter,
        )

    years = get_order_years(args)
    orders = []
    seen_order_ids = set()
    for year in years:
        print(f"Fetching Amazon order history for {year}")
        for order in orders_client.get_orders(year=year, full_details=args.full_details):
            order_id = get_field(order, "order_number")
            if order_id in seen_order_ids:
                continue
            orders.append(order)
            seen_order_ids.add(order_id)
    return orders


def get_order_years(args: argparse.Namespace) -> list[int]:
    if args.year:
        return [args.year]

    if args.start_date:
        start_date = parse_iso_date(args.start_date)
        current_year = date.today().year
        return list(range(start_date.year, current_year + 1))

    return [date.today().year]


def get_transaction_days(args: argparse.Namespace) -> int:
    if not args.start_date:
        return args.transaction_days

    start_date = parse_iso_date(args.start_date)
    return max((date.today() - start_date).days + 1, 1)


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def fetch_missing_transaction_orders(
    orders_client: AmazonOrders,
    orders: list[Any],
    transactions: list[Any],
    supplement_after: str | None,
) -> list[Any]:
    known_order_ids = {get_field(order, "order_number") for order in orders}
    missing_order_ids = []

    for transaction in transactions:
        order_id = get_field(transaction, "order_number")
        completed_date = get_field(transaction, "completed_date")
        completed_date_text = completed_date.isoformat() if hasattr(completed_date, "isoformat") else completed_date
        if not order_id or order_id in known_order_ids:
            continue
        if supplement_after and completed_date_text and completed_date_text < supplement_after:
            continue
        missing_order_ids.append(order_id)
        known_order_ids.add(order_id)

    supplemented_orders = []
    for order_id in missing_order_ids:
        try:
            print(f"Fetching missing order details for {order_id}")
            supplemented_orders.append(orders_client.get_order(order_id))
        except Exception as error:  # noqa: BLE001 - third-party scraper raises mixed exception types.
            print(f"Could not fetch missing order {order_id}: {error}", file=sys.stderr)

    return supplemented_orders


def get_field(value: Any, field_name: str) -> Any:
    if isinstance(value, dict):
        return value.get(field_name)
    return getattr(value, field_name, None)


def to_plain_value(value: Any) -> Any:
    if is_dataclass(value):
        return to_plain_value(asdict(value))

    if isinstance(value, dict):
        return {str(key): to_plain_value(child) for key, child in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [to_plain_value(child) for child in value]

    if hasattr(value, "__dict__"):
        public_values = {
            key: child
            for key, child in vars(value).items()
            if not key.startswith("_") and key not in {"soup", "parsed", "config"}
        }
        return to_plain_value(public_values)

    return value


if __name__ == "__main__":
    main()
