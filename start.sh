#!/bin/bash
cd "$(dirname "$0")"
pip3 install fastapi uvicorn aiosqlite pydantic httpx --break-system-packages -q
python3 api.py
