from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def _read(relative: str) -> str:
    return (FRONTEND / relative).read_text(encoding="utf-8")


def test_app_has_skip_navigation_current_page_and_live_feedback():
    source = _read("App.tsx")
    assert 'className="skip-link" href="#main-content"' in source
    assert 'id="main-content"' in source
    assert 'aria-current={page === item.page ? "page" : undefined}' in source
    assert 'role={toast.tone === "error" ? "alert" : "status"}' in source
    assert 'aria-live={toast.tone === "error" ? "assertive" : "polite"}' in source


def test_shared_modal_has_the_complete_keyboard_focus_contract():
    source = _read("components.tsx")
    modal = source[source.index("export function Modal"):source.index("export function Field")]
    for marker in (
        'role="dialog"',
        'aria-modal="true"',
        'event.key === "Escape"',
        'event.key !== "Tab"',
        "returnFocusRef",
        "document.activeElement",
        "querySelectorAll<HTMLElement>",
        "target?.focus()",
        "useId()",
    ):
        assert marker in modal, marker


def test_focus_is_visibly_global_and_skip_link_becomes_visible():
    source = _read("styles.css")
    assert ":focus-visible" in source
    focus = source[source.index(":focus-visible"):source.index(":focus-visible") + 180]
    assert "outline:" in focus
    assert ".skip-link:focus" in source
    assert "prefers-reduced-motion" in source


def test_progress_exposes_machine_readable_value():
    source = _read("components.tsx")
    progress = source[source.index("export function Progress"):]
    for marker in (
        'role="progressbar"',
        "aria-valuemin={0}",
        "aria-valuemax={100}",
        "aria-valuenow={bounded}",
    ):
        assert marker in progress


def test_ai_drawer_and_confirmation_do_not_leave_hidden_focus_traps():
    source = _read("pages/AI.tsx")
    assert "{panelOpen ? (" in source
    assert 'id="ai-history-panel"' in source
    assert 'aria-controls="ai-history-panel"' in source
    assert 'event.key === "Escape"' in source
    assert "<Modal" in source
    assert "ai-confirm-modal" not in source
    assert 'role="tab"' not in source
    assert 'role="group" aria-label="How to work"' in source
    assert "aria-pressed={workMode === tab.key}" in source


def test_sales_drag_has_keyboard_equivalents_for_edit_and_move():
    source = _read("pages/SalesTracker.tsx")
    card = source[source.index("function SalesCard"):source.index("function SetterTable")]
    assert 'className="sales-card-edit"' in card
    assert "Edit " in card and "aria-label=" in card
    assert "Move " in card and "<select aria-label=" in card
    assert "onKeyDown={keyEdit}" not in card
    assert "tabIndex={0}" not in card


def test_video_effect_controls_work_without_a_mouse():
    source = _read("pages/VideoEditor.tsx")
    assert "Strength for " in source
    assert "onBlur={(event) =>" in source
    assert "earlier in the effect stack" in source
    assert "later in the effect stack" in source
    assert "Remove " in source and " effect" in source


def test_every_frontend_image_declares_alt_text():
    offenders: list[str] = []
    for path in FRONTEND.rglob("*.tsx"):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"<img\\b[^>]*>", source, flags=re.DOTALL):
            if not re.search(r"\\balt\\s*=", match.group(0)):
                offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)[:120]}")
    assert offenders == []


def test_no_pointer_only_generic_click_targets_remain_in_core_shells():
    for relative in ("App.tsx", "components.tsx", "pages/SalesTracker.tsx"):
        source = _read(relative)
        matches = re.findall(
            r"<(?:article|section|li|tr|td|span)\\b[^>]*\\bonClick=",
            source,
            flags=re.DOTALL,
        )
        assert matches == [], (relative, matches)



def test_all_frontend_click_targets_have_a_keyboard_path():
    offenders: list[str] = []
    for path in FRONTEND.rglob("*.tsx"):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(
            r"<(div|span|li|section|article|tr|td)\b[^>]*\bonClick\s*=.*?>",
            source,
            flags=re.DOTALL,
        ):
            tag = match.group(0)
            # A backdrop may be mouse convenience only when it is explicitly
            # absent from the accessibility tree; the same surface must expose
            # an Escape/close button elsewhere (AI drawer is covered separately).
            if 'aria-hidden="true"' in tag:
                continue
            offenders.append(
                f"{path.relative_to(ROOT)}: {re.sub(r'\s+', ' ', tag)[:160]}"
            )
    assert offenders == []


def test_no_positive_tab_order_exists_anywhere_in_frontend():
    offenders: list[str] = []
    for path in FRONTEND.rglob("*.tsx"):
        source = path.read_text(encoding="utf-8")
        if re.search(r"\btabIndex\s*=\s*\{?\s*[1-9]\d*", source):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_fake_role_buttons_require_keyboard_handlers_everywhere():
    offenders: list[str] = []
    for path in FRONTEND.rglob("*.tsx"):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(
            r"<[^>]+\brole\s*=\s*[\"']button[\"'][^>]*>",
            source,
            flags=re.DOTALL,
        ):
            tag = match.group(0)
            if "onKeyDown=" not in tag and "onKeyUp=" not in tag:
                offenders.append(
                    f"{path.relative_to(ROOT)}: {re.sub(r'\s+', ' ', tag)[:160]}"
                )
    assert offenders == []
