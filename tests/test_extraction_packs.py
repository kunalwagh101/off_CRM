from __future__ import annotations

import json

import pytest

from offsetx_apollo_builder.discovery import ScraplingPageParser
from offsetx_apollo_builder.extraction_packs import (
    ExtractionPackError,
    ExtractionPackRegistry,
)


def _registry(*packs):
    return ExtractionPackRegistry.from_data({"version": 1, "packs": list(packs)})


def _people_pack(**overrides):
    pack = {
        "id": "example-people",
        "domains": ["example.com"],
        "record_selector": ".person",
        "fields": {
            "full_name": {"selector": ".name", "mode": "text"},
            "title": {"selector": ".role", "mode": "text"},
            "company": {"selector": ".company", "mode": "text"},
            "email": {"selector": ".email", "mode": "text"},
            "linkedin_url": {
                "selector": "a.linkedin",
                "mode": "attr",
                "attribute": "href",
            },
        },
    }
    pack.update(overrides)
    return pack


def test_a_source_is_added_by_pack_data_without_new_parser_code():
    parser = ScraplingPageParser(pack_registry=_registry(_people_pack()))
    page = parser.parse(
        b"""
        <html><head><title>Team</title></head><body>
          <div class="person">
            <span class="name">Asha Rao</span>
            <span class="role">Head of Climate</span>
            <span class="company">Acme Steel</span>
            <span class="email">asha@example.com</span>
            <a class="linkedin" href="https://www.linkedin.com/in/asha-rao">profile</a>
          </div>
        </body></html>
        """,
        "https://example.com/team",
    )
    assert len(page.people) == 1
    person = page.people[0]
    assert person.full_name == "Asha Rao"
    assert person.title == "Head of Climate"
    assert person.company == "Acme Steel"
    assert person.email == "asha@example.com"
    assert person.linkedin_url == "https://www.linkedin.com/in/asha-rao"
    assert person.evidence["format"] == "extraction_pack"
    assert person.evidence["pack_id"] == "example-people"


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"version": 1, "packs": [_people_pack(fields={"mystery": {"selector": ".x"}})]}, "unknown fields"),
        (
            {
                "version": 1,
                "packs": [
                    _people_pack(),
                    _people_pack(id="other"),
                ],
            },
            "declared by both",
        ),
        (
            {
                "version": 1,
                "packs": [
                    _people_pack(
                        fields={
                            "full_name": {
                                "selector": ".name",
                                "mode": "python",
                            }
                        }
                    )
                ],
            },
            "unsupported extraction mode",
        ),
        (
            {
                "version": 1,
                "packs": [
                    _people_pack(
                        fields={
                            "full_name": {
                                "selector": ".name",
                                "mode": "attr",
                                "attribute": "onclick",
                            }
                        }
                    )
                ],
            },
            "unsupported attribute",
        ),
    ],
)
def test_invalid_registry_fails_closed_as_one_unit(payload, message):
    with pytest.raises(ExtractionPackError, match=message):
        ExtractionPackRegistry.from_data(payload)



@pytest.mark.parametrize(
    "pack, message",
    [
        (_people_pack(record_selector="div["), "invalid CSS selector"),
        (
            _people_pack(
                fields={
                    "full_name": {
                        "selector": ".name[",
                        "mode": "text",
                    }
                }
            ),
            "invalid CSS selector",
        ),
    ],
)
def test_malformed_css_selector_fails_when_registry_loads(pack, message):
    with pytest.raises(ExtractionPackError, match=message):
        _registry(pack)


def test_an_unmatched_source_keeps_the_existing_jsonld_fallback():
    parser = ScraplingPageParser(pack_registry=_registry(_people_pack()))
    page = parser.parse(
        b"""
        <html><head><title>Public profile</title></head><body>
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Person","name":"Mira Sen",
         "jobTitle":"Director","worksFor":{"name":"North Star"}}
        </script>
        </body></html>
        """,
        "https://other.example.org/profile",
    )
    assert [person.full_name for person in page.people] == ["Mira Sen"]
    assert page.people[0].evidence["format"] == "schema_org_person"


def test_pack_is_pure_data_and_unknown_registry_keys_are_rejected(tmp_path):
    path = tmp_path / "packs.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "packs": [_people_pack()],
                "python": "import os",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ExtractionPackError, match="unknown keys"):
        ExtractionPackRegistry.from_file(path)


def test_subdomain_uses_parent_domain_pack():
    registry = _registry(_people_pack())
    assert registry.match("https://careers.example.com/team").id == "example-people"
