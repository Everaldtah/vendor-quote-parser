# Vendor Quote Parser

**Stop wasting hours comparing vendor quotes in spreadsheets.** Upload quotes in any format — CSV, JSON, or plain text — and get an instant side-by-side comparison with the cheapest vendor highlighted.

## The Problem

Procurement teams receive vendor quotes in a dozen different formats: PDFs, Excel sheets, copy-pasted emails, and custom portals. Normalizing all of them into a comparable format takes 2–4 hours per RFQ cycle. Multiply that by dozens of purchases per month and you're hemorrhaging time and making decisions on incomplete data.

## What It Does

- Accepts quotes as **CSV, JSON, or unstructured text**
- Auto-detects fields: item descriptions, SKUs, quantities, unit prices, totals
- Normalizes currencies and handles unit aliases (pcs, units, ea)
- Generates a **side-by-side comparison** with item-level and total-level breakdowns
- Highlights the cheapest vendor and calculates **potential savings**
- Extracts metadata: delivery days, payment terms, expiry dates
- REST API for integration with procurement workflows

## Features

- Multi-format parsing (CSV, JSON, free text)
- Vendor comparison matrix with item-level winners
- Savings calculation
- Session management (group quotes by RFQ)
- Web UI + REST API
- Webhook/Slack alerts (via env config)

## Tech Stack

- **Backend**: Python 3.11+, FastAPI
- **Parsing**: Custom regex + CSV/JSON engines
- **Server**: Uvicorn (ASGI)

## Installation

```bash
git clone https://github.com/Everaldtah/vendor-quote-parser.git
cd vendor-quote-parser
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Usage

### Start the Server

```bash
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000 — use the web UI or explore the API at http://localhost:8000/docs

### Run the Demo (No Server Required)

```bash
python demo.py
```

### API Usage

**Upload and compare quotes:**
```bash
curl -X POST http://localhost:8000/upload \
  -F "files=@vendor_a.csv" \
  -F "files=@vendor_b.txt" \
  -F "session_id=rfq-2026-04"
```

**Parse raw text:**
```bash
curl -X POST http://localhost:8000/parse-text \
  -H "Content-Type: application/json" \
  -d '{"text": "Widget A - $12.50\nWidget B - $8.00", "vendor_name": "ACME Corp"}'
```

**Compare stored session:**
```bash
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{"session_id": "rfq-2026-04"}'
```

## CSV Format (Recommended)

```csv
Item,Qty,Unit Price,Total
Steel Pipe 2-inch,100,12.50,1250.00
Safety Gloves L,50,8.00,400.00
```

Header names are flexible — the parser recognizes common aliases (description, product, part, SKU, rate, cost, etc.)

## Monetization Model

| Plan | Price | Features |
|------|-------|----------|
| Free | $0 | 5 comparisons/month, 2 vendors |
| Starter | $29/mo | 50 comparisons, 5 vendors, CSV export |
| Pro | $79/mo | Unlimited, Slack alerts, API access |
| Enterprise | $299/mo | SSO, audit logs, custom integrations |

**Target customers**: procurement managers, operations teams, construction companies, manufacturing firms, IT departments with regular vendor RFQ cycles.

## Roadmap

- [ ] PDF parsing (pdfplumber integration)
- [ ] Email import (Gmail/Outlook plugin)
- [ ] Historical pricing trends
- [ ] Supplier scorecards
- [ ] ERP integrations (SAP, Oracle)

## License

MIT
