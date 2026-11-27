"""WP1 must not click a backup form while Settings is still loading."""
from __future__ import annotations

import os
import shutil

import pytest

from scripts.qa.wp1_browser_gate import wait_for_backup_panel


def test_waits_for_settings_to_settle_before_returning_backup_panel():
    chromium = os.getenv("OFF_CRM_QA_CHROMIUM") or next(
        (path for name in ("chromium", "google-chrome", "chromium-browser")
         if (path := shutil.which(name))), None,
    )
    if chromium is None:
        pytest.skip("Requires Chromium for the WP1 browser timing regression")
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as instance:
        with instance.chromium.launch(
            executable_path=chromium, headless=True, args=["--disable-dev-shm-usage"],
        ) as browser:
            page = browser.new_page()
            page.set_content('''
                <div class="settings-grid">
                    <div id="loading" aria-busy="true">Loading</div>
                    <section><h2>Encrypted backup</h2>
                      <button type="button">Create encrypted backup</button>
                    </section>
                </div>
                <script>
                  setTimeout(() => {
                    document.getElementById('loading').remove();
                    document.querySelector('section').dataset.ready = 'true';
                  }, 1200);
                </script>
            ''')
            panel = wait_for_backup_panel(page)
            assert panel.get_attribute("data-ready") == "true"
            assert panel.get_by_role("button", name="Create encrypted backup").is_visible()
