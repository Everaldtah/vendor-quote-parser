"""
Demo script — runs a local comparison of two vendor quotes without starting the server.
Usage: python demo.py
"""

from parser_engine import QuoteParser, QuoteComparator

VENDOR_A_CSV = """Item,Qty,Unit Price,Total
Steel Pipe 2-inch,100,12.50,1250.00
Bolts M10 x 50mm,500,0.45,225.00
Safety Gloves L,50,8.00,400.00
Hard Hat Yellow,20,22.00,440.00
"""

VENDOR_B_TEXT = """
From: BuildRight Supplies Inc.
Date: 2026-04-20
Valid Until: 2026-05-20
Delivery: 5 days
Payment Terms: Net 30

Steel Pipe 2-inch - $11.80 x 100 units
Bolts M10 x 50mm - $0.50 x 500 units
Safety Gloves L - $7.50 x 50 units
Hard Hat Yellow - $25.00 x 20 units

Total: $2,165.00
"""

VENDOR_C_JSON = """{
  "vendor": "FastBuild Co.",
  "currency": "USD",
  "delivery_days": 3,
  "payment_terms": "Net 15",
  "valid_until": "2026-05-15",
  "line_items": [
    {"description": "Steel Pipe 2-inch", "qty": 100, "unit_price": 13.20, "total": 1320.00},
    {"description": "Bolts M10 x 50mm", "qty": 500, "unit_price": 0.42, "total": 210.00},
    {"description": "Safety Gloves L", "qty": 50, "unit_price": 7.80, "total": 390.00},
    {"description": "Hard Hat Yellow", "qty": 20, "unit_price": 21.50, "total": 430.00}
  ],
  "grand_total": 2350.00
}"""


def main():
    parser = QuoteParser()
    comparator = QuoteComparator()

    print("=" * 60)
    print("VENDOR QUOTE PARSER — DEMO")
    print("=" * 60)

    quotes = [
        parser.parse(VENDOR_A_CSV, filename="vendor_a_steelco.csv"),
        parser.parse(VENDOR_B_TEXT, filename="buildright_quote.txt"),
        parser.parse(VENDOR_C_JSON, filename="fastbuild.json"),
    ]

    for q in quotes:
        print(f"\n📋 {q['vendor_name']} — Grand Total: ${q['grand_total']:,.2f} {q['currency']}")
        print(f"   Items: {len(q['line_items'])} | Delivery: {q.get('delivery_days', 'N/A')} days | Terms: {q.get('payment_terms') or 'N/A'}")
        for item in q["line_items"]:
            print(f"   - {item['description']}: {item['qty']} x ${item['unit_price']:.2f} = ${item['total']:.2f}")

    print("\n" + "=" * 60)
    print("COMPARISON RESULTS")
    print("=" * 60)

    result = comparator.compare(quotes)

    print(f"\n🏆 CHEAPEST VENDOR: {result['cheapest_vendor']}")
    print(f"💰 POTENTIAL SAVINGS: ${result['potential_savings']:,.2f}")
    print(f"\n💡 RECOMMENDATION: {result['recommendation']}")

    print("\nVendor Totals:")
    for t in sorted(result["vendor_totals"], key=lambda x: x["grand_total"]):
        flag = " ← BEST PRICE" if t["vendor"] == result["cheapest_vendor"] else ""
        print(f"  {t['vendor']:30s} ${t['grand_total']:>10,.2f}{flag}")

    print("\nItem-Level Winners:")
    for item, winner in result["item_winners"].items():
        print(f"  {item:40s} → {winner}")


if __name__ == "__main__":
    main()
