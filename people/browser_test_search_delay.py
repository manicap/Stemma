"""Playwright regression: run against the isolated synthetic Django server."""
import asyncio
import os

from playwright.async_api import async_playwright, expect


async def check_secondary_results_swap(page, base):
    await page.goto(base + "/osoby/?q=Synthetic")
    field = page.locator("#person-search")
    popup = page.locator("#person-suggestions")
    await expect(popup).to_be_visible()
    # Replay the results fragment included alongside the detail after saving.
    fragment = await page.locator("#person-browser-results").evaluate(
        """results => {
            const copy = results.cloneNode(true);
            copy.setAttribute('hx-swap-oob', 'outerHTML');
            return copy.outerHTML;
        }"""
    )
    old_popup = await popup.element_handle()
    await field.press("Escape")
    await page.evaluate(
        """html => htmx.swap('#person-detail', html, {swapStyle: 'innerHTML'})""",
        fragment,
    )
    assert not await old_popup.evaluate("el => el.isConnected")
    await expect(popup).to_be_hidden()
    await expect(field).to_have_attribute("aria-expanded", "false")
    await expect(field).to_be_focused()
    await field.press("ArrowDown")
    await expect(popup).to_be_visible()
    await expect(field).to_have_attribute("aria-expanded", "true")
    await expect(page.locator(".person-suggestion").first).to_be_focused()


async def main():
    base = os.environ.get("STEMMA_TEST_URL", "http://127.0.0.1:18761")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        for width in (1440, 390):
            page = await browser.new_page(viewport={"width": width, "height": 900})
            if width == 1440:
                await check_secondary_results_swap(page, base)
            for query, expected in (("Synthetic", "SwarmPublic"), ("NoSuchPersonXYZ", "Nebyla nalezena")):
                await page.goto(base + "/osoby/")
                if width == 390 and "is-open" not in (await page.locator("#people-panel").get_attribute("class")):
                    await page.locator("[data-person-list-open]").click()
                field = page.locator("#person-search")
                arrived, release = asyncio.Event(), asyncio.Event()

                async def delay(route):
                    response = await route.fetch()
                    arrived.set()
                    await release.wait()
                    await route.fulfill(response=response)

                await page.route("**/osoby/vysledky/**", delay)
                await page.wait_for_timeout(150)
                await field.fill(query)
                await asyncio.wait_for(arrived.wait(), 8)
                await field.press("Escape")
                release.set()
                await expect(page.locator("#person-suggestions")).to_contain_text(expected)
                await expect(page.locator("#person-suggestions")).to_be_hidden()
                await expect(field).to_have_attribute("aria-expanded", "false")
                await expect(field).to_be_focused()
                if query == "Synthetic":
                    await expect(page.locator("#person-list")).to_contain_text("SwarmPublic")
                else:
                    await expect(page.locator("#person-list .person-list-item")).to_have_count(0)
                await page.unroute_all(behavior="wait")
                await field.fill("Synthetic")
                if query == "Synthetic":
                    await field.fill("SwarmPublic")
                await expect(page.locator("#person-suggestions")).to_be_visible()
                await expect(field).to_have_attribute("aria-expanded", "true")
                if query == "Synthetic":
                    await field.press("ArrowDown")
                    await expect(page.locator("#person-suggestions")).to_be_visible()
                    await expect(page.locator(".person-suggestion").first).to_be_focused()
                    await page.keyboard.press("Escape")
                    await expect(field).to_be_focused()
                    await expect(page.locator("#person-suggestions")).to_be_hidden()
                    await field.press("ArrowDown")
                    await page.keyboard.press("Enter")
                    await expect(page.locator("#person-detail")).to_contain_text("SwarmPublic")
                print(f"PASS width={width} query={query}", flush=True)
            await page.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
