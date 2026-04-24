"""
Vendor Quote Parser - FastAPI application
Parses vendor quotes from PDF/CSV/text and normalizes them for comparison.
"""

import os
import io
import csv
import json
import re
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from parser_engine import QuoteParser, QuoteComparator

app = FastAPI(
    title="Vendor Quote Parser",
    description="Upload vendor quotes in any format and compare them side-by-side",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

parser = QuoteParser()
comparator = QuoteComparator()

# In-memory store for parsed quotes (use a real DB in production)
quote_sessions: dict = {}


class QuoteSession(BaseModel):
    session_id: str
    quotes: List[dict]
    created_at: str


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Vendor Quote Parser</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 900px; margin: 50px auto; padding: 20px; background: #f5f5f5; }
            h1 { color: #2c3e50; }
            .upload-area { background: white; border: 2px dashed #3498db; border-radius: 8px; padding: 40px; text-align: center; margin: 20px 0; }
            .btn { background: #3498db; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
            .btn:hover { background: #2980b9; }
            .result { background: white; border-radius: 8px; padding: 20px; margin-top: 20px; }
            table { width: 100%; border-collapse: collapse; }
            th { background: #3498db; color: white; padding: 10px; text-align: left; }
            td { padding: 10px; border-bottom: 1px solid #eee; }
            .winner { background: #d4edda; font-weight: bold; }
            .api-docs { margin-top: 30px; background: white; border-radius: 8px; padding: 20px; }
            code { background: #f8f9fa; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <h1>Vendor Quote Parser</h1>
        <p>Upload vendor quotes in CSV or text format and get instant side-by-side comparison with the best deal highlighted.</p>

        <div class="upload-area">
            <h3>Upload Quote Files</h3>
            <form id="uploadForm" enctype="multipart/form-data">
                <input type="file" name="files" multiple accept=".csv,.txt,.json" id="fileInput">
                <br><br>
                <input type="text" name="session_id" placeholder="Session name (optional)" style="padding:8px; width:200px;">
                <br><br>
                <button type="submit" class="btn">Parse & Compare Quotes</button>
            </form>
        </div>

        <div id="results"></div>

        <div class="api-docs">
            <h3>API Endpoints</h3>
            <ul>
                <li><code>POST /upload</code> - Upload quote files for parsing</li>
                <li><code>POST /compare</code> - Compare quotes by session ID</li>
                <li><code>GET /sessions/{session_id}</code> - Retrieve parsed quotes</li>
                <li><code>POST /parse-text</code> - Parse raw quote text directly</li>
                <li><a href="/docs">Swagger API Docs →</a></li>
            </ul>
        </div>

        <script>
        document.getElementById('uploadForm').onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const res = await fetch('/upload', { method: 'POST', body: formData });
            const data = await res.json();
            document.getElementById('results').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
        };
        </script>
    </body>
    </html>
    """


@app.post("/upload")
async def upload_quotes(
    files: List[UploadFile] = File(...),
    session_id: Optional[str] = Form(None),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    if not session_id:
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    parsed_quotes = []
    errors = []

    for file in files:
        content = await file.read()
        try:
            text = content.decode("utf-8", errors="replace")
            quote = parser.parse(text, filename=file.filename)
            quote["filename"] = file.filename
            parsed_quotes.append(quote)
        except Exception as e:
            errors.append({"file": file.filename, "error": str(e)})

    if not parsed_quotes:
        raise HTTPException(status_code=422, detail=f"Could not parse any files. Errors: {errors}")

    session_data = {
        "session_id": session_id,
        "quotes": parsed_quotes,
        "created_at": datetime.now().isoformat(),
        "errors": errors,
    }
    quote_sessions[session_id] = session_data

    # Auto-compare if we have multiple quotes
    comparison = None
    if len(parsed_quotes) > 1:
        comparison = comparator.compare(parsed_quotes)

    return {
        "session_id": session_id,
        "parsed_count": len(parsed_quotes),
        "quotes": parsed_quotes,
        "comparison": comparison,
        "errors": errors,
    }


@app.post("/parse-text")
async def parse_text(payload: dict):
    text = payload.get("text", "")
    vendor_name = payload.get("vendor_name", "Unknown Vendor")
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")

    quote = parser.parse(text, filename=vendor_name)
    return {"quote": quote}


@app.post("/compare")
async def compare_quotes(payload: dict):
    session_id = payload.get("session_id")
    if session_id and session_id in quote_sessions:
        quotes = quote_sessions[session_id]["quotes"]
    else:
        quotes = payload.get("quotes", [])

    if len(quotes) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 quotes to compare")

    comparison = comparator.compare(quotes)
    return comparison


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    if session_id not in quote_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return quote_sessions[session_id]


@app.get("/sessions")
async def list_sessions():
    return {
        "sessions": [
            {"session_id": k, "quote_count": len(v["quotes"]), "created_at": v["created_at"]}
            for k, v in quote_sessions.items()
        ]
    }


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
