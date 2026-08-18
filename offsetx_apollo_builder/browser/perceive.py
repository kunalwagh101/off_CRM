"""Turning a page into something a model can act on.

The most important design decision in the browser agent, and the one most
easily got wrong.

**Not raw HTML.** A modern page is 400KB of markup, most of it framework noise,
and handing it to a model costs a fortune to say almost nothing. Worse, it
invites the model to write a CSS selector — and a selector written against a
class called ``css-1x4kf9`` breaks on the next deploy, silently, in a way that
looks like the agent got confused.

**The accessibility tree instead.** Chromium already computes, for every page, a
tree of what the page *means*: this is a button labelled "Send", this is a link
to /pricing, this is a text field labelled "Email". It is what a screen reader
consumes. It is roughly a fiftieth the size of the DOM, it is stable across
restyling, and it is expressed in exactly the vocabulary an instruction is
written in — *click the Send button* rather than *click div > div:nth-child(3)*.

**Numbered handles, not selectors.** Every actionable node gets an integer. The
model says ``click(12)``. It cannot invent a handle, cannot describe an element,
and cannot reach anything the snapshot did not offer — the same closed-vocabulary
rule ``ai/tools.py`` applies to Docker and ``video/effects.py`` applies to
shaders. A stale handle is refused by name rather than clicking whatever now
happens to occupy that spot, which is the failure mode that gets an agent to
delete the wrong record.

---

**What is deliberately dropped.** Nodes with no accessible name and no role
worth acting on; anything invisible; anything outside the viewport's document.
An agent that can see an element a person cannot is an agent that does things
nobody can review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .cdp import CDPConnection

#: Roles worth offering as actions. Everything else in the tree becomes text or
#: is dropped. Kept as a closed set because "anything clickable" on a modern
#: page means every div with a handler, which is most of them.
ACTIONABLE_ROLES = frozenset({
    "button", "link", "textbox", "searchbox", "combobox", "checkbox", "radio",
    "switch", "slider", "spinbutton", "menuitem", "menuitemcheckbox",
    "menuitemradio", "option", "tab", "treeitem", "listbox", "textarea",
})

#: Roles that carry meaning but are not clicked. They become context.
STRUCTURAL_ROLES = frozenset({
    "heading", "paragraph", "StaticText", "list", "listitem", "table", "row",
    "cell", "columnheader", "rowheader", "article", "main", "navigation",
    "banner", "contentinfo", "form", "region", "dialog", "alert", "status",
})

#: How much of one node's text survives into the snapshot. A page can contain a
#: novel and the agent needs the shape of it, not the whole thing — `read` is
#: the tool for the whole thing.
MAX_LABEL_CHARS = 180

#: How many nodes a snapshot may carry. Past this the page is summarised rather
#: than listed: a search-results page with 900 links is not made more usable by
#: giving a model all 900.
MAX_NODES = 400


@dataclass
class Node:
    """One thing on the page the agent can see, and possibly act on."""

    handle: int
    role: str
    name: str
    #: CDP's own id for the accessibility node, used to resolve it back to a
    #: DOM node when the action fires.
    backend_id: int = 0
    value: str = ""
    #: Nesting, so a flat list still reads as a page.
    depth: int = 0
    focused: bool = False
    disabled: bool = False
    checked: str = ""
    url: str = ""

    @property
    def actionable(self) -> bool:
        return self.role in ACTIONABLE_ROLES and not self.disabled

    def to_dict(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "handle": self.handle,
            "role": self.role,
            "name": self.name,
            "depth": self.depth,
        }
        for key, value in (
            ("value", self.value), ("url", self.url), ("checked", self.checked),
        ):
            if value:
                item[key] = value
        if self.focused:
            item["focused"] = True
        if self.disabled:
            item["disabled"] = True
        return item

    def render(self) -> str:
        """One line, as the model sees it."""
        indent = "  " * min(self.depth, 8)
        marker = f"[{self.handle}] " if self.actionable else ""
        parts = [f"{indent}{marker}{self.role}"]
        if self.name:
            parts.append(f'"{self.name}"')
        if self.value:
            parts.append(f"= {self.value!r}")
        if self.checked in ("true", "mixed"):
            parts.append(f"({self.checked})")
        if self.disabled:
            parts.append("(disabled)")
        if self.url:
            parts.append(f"→ {self.url}")
        return " ".join(parts)


@dataclass
class Snapshot:
    """What the page looks like right now, and what can be done to it."""

    url: str = ""
    title: str = ""
    nodes: list[Node] = field(default_factory=list)
    #: True when the page had more than `MAX_NODES` worth of content and this
    #: is the first slice of it. Said out loud rather than silently truncated.
    truncated: bool = False

    @property
    def actions(self) -> list[Node]:
        return [node for node in self.nodes if node.actionable]

    def find(self, handle: int) -> Node:
        for node in self.nodes:
            if node.handle == int(handle):
                return node
        available = ", ".join(str(node.handle) for node in self.actions[:20])
        raise LookupError(
            f"There is no element {handle} on this page. The ones you can act on "
            f"are: {available or 'none'}. Take a fresh snapshot if the page moved."
        )

    def render(self, *, limit: int = MAX_NODES) -> str:
        """The whole page as text, for a prompt.

        Deliberately a *rendering* and not JSON. A model reads an indented
        outline more reliably than it reads a nested object, and every token
        spent on punctuation is a token not spent on the page.
        """
        lines = [f"# {self.title}".rstrip(), f"URL: {self.url}", ""]
        lines.extend(node.render() for node in self.nodes[:limit])
        if self.truncated or len(self.nodes) > limit:
            lines.append("")
            lines.append(
                f"… this page has more than {limit} elements; scroll or search "
                "to reach the rest."
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "truncated": self.truncated,
            "nodes": [node.to_dict() for node in self.nodes],
        }


def _text(property_value: Any) -> str:
    """CDP wraps every value in ``{"type": ..., "value": ...}``."""
    if isinstance(property_value, dict):
        return str(property_value.get("value", "") or "")
    return str(property_value or "")


def _clean(text: str) -> str:
    """Collapse whitespace and cap the length.

    A page's accessible names come from its markup, so they arrive with the
    newlines and indentation of the HTML in them. Left alone they turn a
    forty-line snapshot into four hundred.
    """
    collapsed = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(collapsed) <= MAX_LABEL_CHARS:
        return collapsed
    return collapsed[: MAX_LABEL_CHARS - 1] + "…"


def _properties(raw: dict[str, Any]) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for entry in raw.get("properties") or []:
        name = str(entry.get("name") or "")
        if name:
            found[name] = _text(entry.get("value"))
    return found


def build(raw_nodes: list[dict[str, Any]], *, url: str = "", title: str = "") -> Snapshot:
    """Turn CDP's flat accessibility node list into a snapshot.

    Separated from the fetching so it can be tested against recorded trees with
    no browser in sight — the same split `video/gates.py` uses for probing a
    file, and for the same reason.
    """
    snapshot = Snapshot(url=url, title=title)
    by_id = {str(raw.get("nodeId") or ""): raw for raw in raw_nodes}

    # CDP returns the tree flat and **not in document order** — a link can
    # arrive before the paragraph above it. Walking `childIds` depth-first is
    # what puts the page back in the order a person reads it, and that matters
    # more here than anywhere else: the snapshot is prose to a model, and prose
    # whose sentences are shuffled is prose that gets misread.
    children_of = {
        str(raw.get("nodeId") or ""): [str(child) for child in (raw.get("childIds") or [])]
        for raw in raw_nodes
    }
    has_parent = {child for children in children_of.values() for child in children}
    roots = [
        str(raw.get("nodeId") or "")
        for raw in raw_nodes
        if str(raw.get("nodeId") or "") not in has_parent
    ]

    ordered: list[tuple[dict[str, Any], int]] = []
    seen: set[str] = set()
    stack: list[tuple[str, int]] = [(root, 0) for root in reversed(roots)]
    while stack:
        node_id, depth = stack.pop()
        if node_id in seen or node_id not in by_id:
            continue
        seen.add(node_id)
        ordered.append((by_id[node_id], depth))
        for child in reversed(children_of.get(node_id, [])):
            stack.append((child, depth + 1))
    # A tree with a cycle, or a node whose parent was pruned, would otherwise
    # vanish. Anything the walk missed is appended rather than dropped.
    for raw in raw_nodes:
        if str(raw.get("nodeId") or "") not in seen:
            ordered.append((raw, 0))

    handle = 1
    for raw, depth in ordered:
        if raw.get("ignored"):
            continue
        role = _text(raw.get("role"))
        if not role or role in ("none", "generic", "InlineTextBox", "GenericContainer"):
            continue
        name = _clean(_text(raw.get("name")))
        properties = _properties(raw)
        # A node with neither a role worth acting on nor anything to say is
        # structure, and structure without content is noise.
        if role not in ACTIONABLE_ROLES and not name:
            continue
        if role not in ACTIONABLE_ROLES and role not in STRUCTURAL_ROLES:
            continue

        node = Node(
            handle=handle,
            role=role,
            name=name,
            backend_id=int(raw.get("backendDOMNodeId") or 0),
            value=_clean(_text(raw.get("value"))),
            depth=depth,
            focused=properties.get("focused") == "true",
            disabled=properties.get("disabled") == "true",
            checked=str(properties.get("checked") or ""),
            url=_clean(str(properties.get("url") or "")),
        )
        snapshot.nodes.append(node)
        handle += 1
        if len(snapshot.nodes) >= MAX_NODES:
            snapshot.truncated = True
            break
    return snapshot


async def capture(
    connection: CDPConnection, session_id: str, *, timeout: float = 20.0
) -> Snapshot:
    """Read the live page.

    ``Accessibility.getFullAXTree`` rather than a DOM dump: it is what the
    browser already computed for assistive technology, so it is both far smaller
    and far more stable than the markup it came from.
    """
    await connection.send("Accessibility.enable", session_id=session_id, timeout=timeout)
    tree = await connection.send(
        "Accessibility.getFullAXTree", session_id=session_id, timeout=timeout
    )
    where = await connection.send(
        "Runtime.evaluate",
        {
            "expression": "JSON.stringify({url: location.href, title: document.title})",
            "returnByValue": True,
        },
        session_id=session_id,
        timeout=timeout,
    )
    import json

    try:
        page = json.loads(str(where.get("result", {}).get("value") or "{}"))
    except ValueError:
        page = {}
    return build(
        list(tree.get("nodes") or []),
        url=str(page.get("url") or ""),
        title=str(page.get("title") or ""),
    )
