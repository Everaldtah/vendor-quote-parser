"""
Core parsing and comparison engine for vendor quotes.
Handles CSV, plain text, and structured text formats.
"""

import csv
import io
import re
import json
from typing import List, Dict, Any, Optional


class QuoteParser:
    """Parses vendor quotes from various text formats into a normalized structure."""

    # Common field name aliases
    FIELD_ALIASES = {
        "item": ["item", "product", "description", "service", "part", "sku", "name", "line item"],
        "qty": ["qty", "quantity", "amount", "units", "count", "pcs", "pieces"],
        "unit_price": ["unit price", "unit_price", "price", "rate", "cost", "unit cost", "each", "per unit"],
        "total": ["total", "subtotal", "line total", "extended", "amount", "ext price", "extended price"],
        "sku": ["sku", "part number", "part no", "model", "item code", "product code", "ref"],
        "notes": ["notes", "note", "comment", "remarks", "terms"],
    }

    def parse(self, text: str, filename: str = "") -> Dict[str, Any]:
        """Auto-detect format and parse quote into normalized dict."""
        text = text.strip()

        if filename.endswith(".json") or (text.startswith("{") or text.startswith("[")):
            return self._parse_json(text, filename)

        if self._looks_like_csv(text):
            return self._parse_csv(text, filename)

        return self._parse_freetext(text, filename)

    def _looks_like_csv(self, text: str) -> bool:
        """Heuristic: check if text is CSV-like."""
        lines = text.strip().split("\n")
        if len(lines) < 2:
            return False
        comma_counts = [line.count(",") for line in lines[:5]]
        return max(comma_counts) >= 2 and len(set(comma_counts)) <= 2

    def _normalize_header(self, header: str) -> str:
        """Map a raw header to a canonical field name."""
        header_lower = header.lower().strip()
        for canonical, aliases in self.FIELD_ALIASES.items():
            if any(alias in header_lower for alias in aliases):
                return canonical
        return header_lower.replace(" ", "_")

    def _parse_csv(self, text: str, filename: str) -> Dict[str, Any]:
        reader = csv.DictReader(io.StringIO(text))
        raw_headers = reader.fieldnames or []
        header_map = {h: self._normalize_header(h) for h in raw_headers}

        line_items = []
        vendor_name = ""
        currency = "USD"

        for row in reader:
            normalized = {}
            for raw_h, val in row.items():
                key = header_map.get(raw_h, raw_h.lower())
                normalized[key] = val.strip() if val else ""

            # Try to extract numeric values
            item = {
                "description": normalized.get("item", normalized.get("description", "")),
                "sku": normalized.get("sku", ""),
                "qty": self._to_float(normalized.get("qty", "1")),
                "unit_price": self._to_float(normalized.get("unit_price", "0")),
                "total": self._to_float(normalized.get("total", "0")),
                "notes": normalized.get("notes", ""),
            }

            # Calculate total if missing
            if item["total"] == 0 and item["qty"] and item["unit_price"]:
                item["total"] = round(item["qty"] * item["unit_price"], 2)

            # Detect currency
            for val in normalized.values():
                if "$" in str(val):
                    currency = "USD"
                elif "€" in str(val):
                    currency = "EUR"
                elif "£" in str(val):
                    currency = "GBP"

            if item["description"] or item["unit_price"]:
                line_items.append(item)

        grand_total = sum(i["total"] for i in line_items)

        return {
            "vendor_name": vendor_name or self._extract_vendor_from_filename(filename),
            "currency": currency,
            "line_items": line_items,
            "subtotal": grand_total,
            "taxes": 0.0,
            "grand_total": grand_total,
            "delivery_days": None,
            "valid_until": None,
            "payment_terms": "",
            "raw_format": "csv",
        }

    def _parse_json(self, text: str, filename: str) -> Dict[str, Any]:
        data = json.loads(text)
        if isinstance(data, list):
            data = {"line_items": data}

        line_items = data.get("line_items", data.get("items", []))
        normalized_items = []
        for item in line_items:
            normalized_items.append({
                "description": item.get("description", item.get("item", item.get("name", ""))),
                "sku": item.get("sku", item.get("part_number", "")),
                "qty": self._to_float(item.get("qty", item.get("quantity", 1))),
                "unit_price": self._to_float(item.get("unit_price", item.get("price", 0))),
                "total": self._to_float(item.get("total", item.get("line_total", 0))),
                "notes": item.get("notes", ""),
            })
            if normalized_items[-1]["total"] == 0:
                normalized_items[-1]["total"] = round(
                    normalized_items[-1]["qty"] * normalized_items[-1]["unit_price"], 2
                )

        grand_total = self._to_float(data.get("grand_total", data.get("total", sum(i["total"] for i in normalized_items))))

        return {
            "vendor_name": data.get("vendor", data.get("vendor_name", self._extract_vendor_from_filename(filename))),
            "currency": data.get("currency", "USD"),
            "line_items": normalized_items,
            "subtotal": self._to_float(data.get("subtotal", grand_total)),
            "taxes": self._to_float(data.get("tax", data.get("taxes", 0))),
            "grand_total": grand_total,
            "delivery_days": data.get("delivery_days"),
            "valid_until": data.get("valid_until", data.get("expiry")),
            "payment_terms": data.get("payment_terms", ""),
            "raw_format": "json",
        }

    def _parse_freetext(self, text: str, filename: str) -> Dict[str, Any]:
        """Parse unstructured text quote using regex heuristics."""
        lines = text.split("\n")
        vendor_name = self._extract_vendor_from_filename(filename)
        currency = "USD"
        line_items = []
        payment_terms = ""
        delivery_days = None
        valid_until = None

        # Try to detect vendor name from first few lines
        for line in lines[:5]:
            if re.search(r"(from|vendor|supplier|company|inc|llc|ltd|corp):", line, re.I):
                match = re.sub(r"(from|vendor|supplier|company):?", "", line, flags=re.I).strip()
                if match:
                    vendor_name = match

        # Detect currency symbols
        text_lower = text.lower()
        if "€" in text or "eur" in text_lower:
            currency = "EUR"
        elif "£" in text or "gbp" in text_lower:
            currency = "GBP"

        # Extract line items: lines with a price pattern
        price_pattern = re.compile(
            r"(.+?)\s+(?:x\s*)?(\d+(?:\.\d+)?)\s+(?:units?|pcs|ea|each)?\s*[@x\*]?\s*\$?([\d,]+(?:\.\d{2})?)",
            re.I,
        )
        simple_price_pattern = re.compile(
            r"(.+?)\s+[-–:]\s+\$?([\d,]+(?:\.\d{2})?)", re.I
        )

        for line in lines:
            line = line.strip()
            if not line or len(line) < 4:
                continue

            # Skip header-like lines
            if re.match(r"^(item|description|product|qty|price|total|#)", line, re.I):
                continue

            m = price_pattern.match(line)
            if m:
                desc, qty, price = m.group(1).strip(), float(m.group(2)), float(m.group(3).replace(",", ""))
                line_items.append({
                    "description": desc,
                    "sku": "",
                    "qty": qty,
                    "unit_price": price,
                    "total": round(qty * price, 2),
                    "notes": "",
                })
                continue

            m2 = simple_price_pattern.match(line)
            if m2:
                desc, price = m2.group(1).strip(), float(m2.group(2).replace(",", ""))
                line_items.append({
                    "description": desc,
                    "sku": "",
                    "qty": 1,
                    "unit_price": price,
                    "total": price,
                    "notes": "",
                })

            # Extract metadata
            if re.search(r"payment.terms?", line, re.I):
                payment_terms = line
            if re.search(r"deliver\w+\s+(\d+)\s+days?", line, re.I):
                m = re.search(r"(\d+)\s+days?", line, re.I)
                if m:
                    delivery_days = int(m.group(1))
            if re.search(r"valid.until|expires?|expiry", line, re.I):
                valid_until = re.sub(r"valid.until|expires?:?|expiry:?", "", line, flags=re.I).strip()

        # Extract grand total from text
        total_match = re.search(r"(?:grand\s+)?total[:\s]+\$?([\d,]+(?:\.\d{2})?)", text, re.I)
        grand_total = float(total_match.group(1).replace(",", "")) if total_match else sum(i["total"] for i in line_items)

        tax_match = re.search(r"tax[:\s]+\$?([\d,]+(?:\.\d{2})?)", text, re.I)
        taxes = float(tax_match.group(1).replace(",", "")) if tax_match else 0.0

        return {
            "vendor_name": vendor_name,
            "currency": currency,
            "line_items": line_items,
            "subtotal": round(grand_total - taxes, 2),
            "taxes": taxes,
            "grand_total": grand_total,
            "delivery_days": delivery_days,
            "valid_until": valid_until,
            "payment_terms": payment_terms,
            "raw_format": "text",
        }

    def _to_float(self, val) -> float:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            cleaned = re.sub(r"[^\d.\-]", "", val)
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0

    def _extract_vendor_from_filename(self, filename: str) -> str:
        name = re.sub(r"\.(csv|txt|json|pdf)$", "", filename, flags=re.I)
        name = re.sub(r"[_\-]quote.*$", "", name, flags=re.I)
        return name.replace("_", " ").replace("-", " ").title() or "Unknown Vendor"


class QuoteComparator:
    """Compares multiple parsed quotes and identifies the best deal."""

    def compare(self, quotes: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not quotes:
            return {}

        # Find common items across quotes
        all_descriptions = set()
        for q in quotes:
            for item in q.get("line_items", []):
                desc = item.get("description", "").strip().lower()
                if desc:
                    all_descriptions.add(desc)

        # Build comparison matrix
        item_matrix = {}
        for desc in all_descriptions:
            item_matrix[desc] = {}
            for q in quotes:
                vendor = q.get("vendor_name", "Unknown")
                for item in q.get("line_items", []):
                    if item.get("description", "").strip().lower() == desc:
                        item_matrix[desc][vendor] = {
                            "unit_price": item.get("unit_price", 0),
                            "qty": item.get("qty", 1),
                            "total": item.get("total", 0),
                        }

        # Find winner per item
        item_winners = {}
        for desc, vendors in item_matrix.items():
            if vendors:
                winner = min(vendors.items(), key=lambda x: x[1]["unit_price"])
                item_winners[desc] = winner[0]

        # Overall totals comparison
        totals = [
            {
                "vendor": q.get("vendor_name", "Unknown"),
                "grand_total": q.get("grand_total", 0),
                "currency": q.get("currency", "USD"),
                "delivery_days": q.get("delivery_days"),
                "payment_terms": q.get("payment_terms", ""),
                "line_item_count": len(q.get("line_items", [])),
            }
            for q in quotes
        ]

        valid_totals = [t for t in totals if t["grand_total"] > 0]
        cheapest_vendor = min(valid_totals, key=lambda x: x["grand_total"])["vendor"] if valid_totals else None
        most_expensive = max(valid_totals, key=lambda x: x["grand_total"])["vendor"] if valid_totals else None

        savings = 0
        if len(valid_totals) >= 2:
            sorted_totals = sorted(valid_totals, key=lambda x: x["grand_total"])
            savings = round(sorted_totals[-1]["grand_total"] - sorted_totals[0]["grand_total"], 2)

        return {
            "vendor_totals": totals,
            "cheapest_vendor": cheapest_vendor,
            "most_expensive_vendor": most_expensive,
            "potential_savings": savings,
            "item_comparison": item_matrix,
            "item_winners": item_winners,
            "recommendation": (
                f"Choose {cheapest_vendor}. You save {savings} {valid_totals[0]['currency']} "
                f"compared to the most expensive option."
            ) if cheapest_vendor and savings > 0 else "All vendors are priced similarly.",
        }
