"""
run_server.py — SiteGuard backend server launcher.
Sets WindowsSelectorEventLoopPolicy on win32 BEFORE uvicorn initializes its event loop,
enabling aiomqtt / MQTT consumer socket polling on Windows.
"""
from __future__ import annotations

import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

def main():
    port = int(os.environ.get("SITEGUARD_PORT", os.environ.get("PORT", "8000")))
    host = os.environ.get("SITEGUARD_HOST", "127.0.0.1")
    uvicorn.run("app.main:app", host=host, port=port, loop="asyncio")

if __name__ == "__main__":
    main()
