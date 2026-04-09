"""Record a video demo of the SignalFlow dashboard using Playwright."""

import asyncio
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:8502"

# Pages in navigation order (Streamlit multipage nav)
PAGES = [
    {"name": "SignalFlow", "wait": 4000},          # Landing
    {"name": "Command Center", "wait": 5000},      # Overview
    {"name": "Portfolio", "wait": 5000},            # Portfolio
    {"name": "Market Scanner", "wait": 4000},       # Signals
    {"name": "Agent Performance", "wait": 4000},    # Analytics
    {"name": "Whale Intelligence", "wait": 4000},   # KOL Tracker
]


async def scroll_page(page, steps=3, delay=800):
    """Smoothly scroll down the page in steps, then back up."""
    viewport_height = page.viewport_size["height"]
    for i in range(1, steps + 1):
        await page.mouse.wheel(0, viewport_height * 0.6)
        await page.wait_for_timeout(delay)
    # Scroll back to top
    await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    await page.wait_for_timeout(600)


async def click_nav_item(page, name):
    """Click a navigation item in Streamlit's sidebar nav."""
    # Try clicking the nav link by text
    nav_link = page.locator(f'a:has-text("{name}")').first
    try:
        await nav_link.click(timeout=3000)
        return True
    except Exception:
        pass

    # Fallback: try the sidebar nav items
    nav_link = page.locator(f'[data-testid="stSidebarNav"] a:has-text("{name}")').first
    try:
        await nav_link.click(timeout=3000)
        return True
    except Exception:
        pass

    # Last resort: look for any element with the page name
    elements = page.get_by_text(name, exact=False)
    count = await elements.count()
    for i in range(count):
        el = elements.nth(i)
        tag = await el.evaluate("el => el.tagName")
        if tag == "A" or tag == "SPAN":
            try:
                await el.click(timeout=2000)
                return True
            except Exception:
                continue
    return False


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir="/Users/bhaveshgupta01/signalflow/demo_video",
            record_video_size={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        # Load the app
        print("Loading SignalFlow dashboard...")
        await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # Wait for Streamlit to fully render
        try:
            await page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=15000)
        except Exception:
            print("Warning: Could not find Streamlit container, continuing anyway")

        # Expand sidebar if collapsed
        try:
            sidebar_btn = page.locator('[data-testid="collapsedControl"]')
            if await sidebar_btn.is_visible(timeout=2000):
                await sidebar_btn.click()
                await page.wait_for_timeout(500)
        except Exception:
            pass

        # Tour each page
        for i, pg in enumerate(PAGES):
            name = pg["name"]
            wait = pg["wait"]

            print(f"  [{i+1}/{len(PAGES)}] Navigating to: {name}")

            if i == 0:
                # Already on landing page, just wait and scroll
                await page.wait_for_timeout(wait)
                await scroll_page(page, steps=5, delay=1000)
                await page.wait_for_timeout(1000)
            else:
                clicked = await click_nav_item(page, name)
                if clicked:
                    await page.wait_for_timeout(wait)
                    await scroll_page(page, steps=4, delay=900)
                    await page.wait_for_timeout(1000)
                else:
                    print(f"    WARNING: Could not navigate to {name}")

        # Final pause on last page
        await page.wait_for_timeout(2000)

        # Close to finalize recording
        print("Finalizing video...")
        await context.close()
        await browser.close()

    print("Done! Video saved in demo_video/")


if __name__ == "__main__":
    asyncio.run(main())
