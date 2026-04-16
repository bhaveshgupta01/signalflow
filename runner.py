"""SignalFlow entry point — event-driven agent loop.

Starts async trigger tasks that push events onto an EventBus,
consumed by the agent in a single loop.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from google import genai

from agent import handle_event
from config import (
    GEMINI_API_KEY,
    GCP_PROJECT,
    GCP_LOCATION,
    USE_VERTEX,
)
from db import init_db
from event_bus import EventBus
from mcp_client import BobaClient
from triggers import (
    cross_chain_trigger,
    funding_trigger,
    hl_whale_trigger,
    kol_trigger,
    polymarket_trigger,
    portfolio_trigger,
    token_discovery_trigger,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("signalflow")


def _create_gemini_client() -> genai.Client:
    """Create Gemini client — Vertex AI (paid) or API key (free tier)."""
    if USE_VERTEX:
        logger.info(
            "Using Vertex AI backend (project=%s, location=%s)",
            GCP_PROJECT,
            GCP_LOCATION,
        )
        return genai.Client(
            vertexai=True,
            project=GCP_PROJECT,
            location=GCP_LOCATION,
        )
    else:
        if not GEMINI_API_KEY:
            logger.error(
                "GEMINI_API_KEY is not set and USE_VERTEX=false. Add it to .env"
            )
            sys.exit(1)
        logger.info("Using Gemini API key backend")
        return genai.Client(api_key=GEMINI_API_KEY)


async def _connect_boba_with_retry(max_retries: int = 5) -> BobaClient:
    """Connect to Boba MCP with retry logic."""
    boba = BobaClient()
    for attempt in range(1, max_retries + 1):
        try:
            await boba.connect()
            logger.info("Boba MCP connected — %d tools available", len(boba.tools_for_claude))
            return boba
        except Exception as e:
            if attempt == max_retries:
                logger.error("Failed to connect to Boba MCP after %d attempts", max_retries)
                raise
            delay = min(10 * attempt, 60)
            logger.warning(
                "Boba connection attempt %d/%d failed: %s — retrying in %ds",
                attempt, max_retries, e, delay,
            )
            await asyncio.sleep(delay)
    raise RuntimeError("Unreachable")


async def _run() -> None:
    # Initialise persistence
    init_db()
    logger.info("Database initialised")

    # Connect to Boba MCP with retry
    boba = await _connect_boba_with_retry()

    # Gemini client
    client = _create_gemini_client()

    # Event bus
    bus = EventBus()

    # Start trigger tasks
    asyncio.create_task(polymarket_trigger(boba, bus))
    asyncio.create_task(kol_trigger(boba, bus))
    asyncio.create_task(funding_trigger(boba, bus))
    asyncio.create_task(hl_whale_trigger(boba, bus))
    asyncio.create_task(token_discovery_trigger(boba, bus))
    asyncio.create_task(cross_chain_trigger(boba, bus))
    asyncio.create_task(portfolio_trigger(boba, bus))
    logger.info("7 triggers started. Waiting for events...")

    # Agent loop — event-driven
    consecutive_errors = 0
    try:
        while True:
            event = await bus.consume()
            logger.info(
                "Event [%s]: %s",
                event.trigger.value,
                str(event.data)[:100],
            )
            try:
                await handle_event(client, boba, event)
                consecutive_errors = 0
            except Exception:
                consecutive_errors += 1
                logger.exception("Error handling event (consecutive: %d)", consecutive_errors)
                if consecutive_errors > 10:
                    logger.error("Too many consecutive errors — attempting Boba reconnect")
                    try:
                        await boba.disconnect()
                        boba = await _connect_boba_with_retry()
                        consecutive_errors = 0
                    except Exception:
                        logger.exception("Reconnection failed")
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
        await boba.disconnect()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
