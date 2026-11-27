"""Readiness for the real WP1 Settings browser acceptance path."""
from playwright.sync_api import expect


def wait_for_backup_panel(page):
    title = page.get_by_role("heading", name="Encrypted backup", exact=True)
    panel = page.locator("section").filter(has=title)
    expect(title).to_be_visible(timeout=15_000)
    # Settings panels load concurrently and can move the form during a click.
    # This disposable app has no continuous polling; wait for initial reads
    # and their rendered loading indicators before interacting with the form.
    page.wait_for_load_state("networkidle", timeout=15_000)
    expect(page.locator('.settings-grid [aria-busy="true"]')).to_have_count(0, timeout=15_000)
    expect(panel.get_by_role("button", name="Create encrypted backup")).to_be_enabled()
    return panel
