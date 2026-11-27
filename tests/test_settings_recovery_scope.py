"""Installation recovery forms must survive a campaign-selection change."""
import re
from pathlib import Path


def test_settings_is_not_remounted_on_campaign_selection():
    app = (Path(__file__).resolve().parents[1] / "frontend/src/App.tsx").read_text()
    pages = re.search(r'const campaignScopedPages = new Set<Page>\(\[([\s\S]*?)\]\);', app)
    assert pages
    names = set(re.findall(r'"([^"]+)"', pages.group(1)))
    assert "settings" not in names
    assert {"contacts", "drafts", "videoeditor"} <= names
