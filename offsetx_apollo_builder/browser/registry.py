"""Validated owner declarations for browser identity, pacing and budgets.

An override replaces the registry in full. The packaged file remains available
in installed wheels, so a working directory is never a configuration dependency.
"""
from __future__ import annotations

import ipaddress
import math
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

DEFAULT_PATH = Path(__file__).with_name('platforms.yaml')
REQUIRED = {'id', 'label', 'login_url', 'home_url', 'signed_in', 'signed_out',
            'domains', 'min_seconds_between_actions', 'unattended',
            'actions_per_hour', 'actions_per_day'}
OPTIONAL = {'note', 'refuse', 'confirm'}


class _UniqueLoader(yaml.SafeLoader):
    """Ambiguous duplicate keys must not silently widen an owner policy."""


def _mapping(loader: _UniqueLoader, node: yaml.MappingNode) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key in result:
            raise ValueError('duplicate or non-text YAML mapping key')
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


class RegistryError(ValueError):
    """An owner declaration cannot safely be used. No partial registry loads."""


def _host(value: object) -> str:
    if not isinstance(value, str) or value != value.lower() or len(value) > 253:
        raise ValueError('domains must be lowercase host names')
    labels = value.split('.')
    if len(labels) < 2 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels):
        raise ValueError('domains must be explicit public host names')
    if value.endswith(('.internal', '.localhost', '.local')):
        raise ValueError('local domains are not permitted')
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return value
    if not address.is_global:
        raise ValueError('private addresses are not permitted')
    return value


def _url(value: object) -> str:
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('URLs must be HTTPS URLs without whitespace')
    url = urlsplit(value)
    if url.scheme != 'https' or not url.hostname or url.username or url.password:
        raise ValueError('URLs must use HTTPS without credentials')
    if url.port not in (None, 443):
        raise ValueError('URLs must use the HTTPS port')
    _host(url.hostname)
    return value


def _strings(value: object, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError('expected a list of names')
    if any(not isinstance(v, str) or not v.strip() or len(v) > 300 for v in value):
        raise ValueError('names must be nonempty strings of at most 300 characters')
    return value


def _rule(row: dict[str, Any]) -> None:
    pace = row['min_seconds_between_actions']
    if type(pace) not in (int, float) or not math.isfinite(pace) or pace < 0:
        raise ValueError('pace must be a finite nonnegative number')
    if type(row['unattended']) is not bool:
        raise ValueError('unattended must be a boolean')
    for field in ('refuse', 'confirm'):
        _strings(row.get(field, []))


def load_registry(path: Path | str | None = None) -> dict[str, Any]:
    source = Path(path or os.environ.get('OFFSETX_BROWSER_PLATFORMS') or DEFAULT_PATH)
    try:
        if source.stat().st_size > 262144:
            raise ValueError('registry exceeds 256 KiB')
        data = yaml.load(source.read_text(encoding='utf-8'), Loader=_UniqueLoader)
        if not isinstance(data, dict) or set(data) - {'platforms', 'extra_rules', 'budget_aliases', 'extra_budgets'}:
            raise ValueError('expected a registry with platforms')
        if not isinstance(data.get('platforms'), list) or not data['platforms']:
            raise ValueError('platforms must be a nonempty list')
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise RegistryError(f'Cannot load browser registry {source.name}: {exc}') from exc
    seen_ids: set[str] = set()
    seen_domains: set[str] = set()
    for row in data['platforms']:
        name = row.get('id', '<unnamed>') if isinstance(row, dict) else '<unnamed>'
        try:
            if not isinstance(row, dict) or REQUIRED - row.keys() or row.keys() - REQUIRED - OPTIONAL:
                raise ValueError('missing required fields or unknown fields')
            if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', name) or name in seen_ids:
                raise ValueError('invalid or duplicate platform id')
            if not isinstance(row['label'], str) or not row['label'].strip():
                raise ValueError('label must be nonempty')
            if not isinstance(row.get('note', ''), str):
                raise ValueError('note must be text')
            seen_ids.add(name)
            for field in ('login_url', 'home_url'):
                _url(row[field])
            for field in ('signed_in', 'signed_out'):
                row[field] = [s.lower() for s in _strings(row[field], nonempty=True)]
            for domain in _strings(row['domains'], nonempty=True):
                _host(domain)
                if domain in seen_domains:
                    raise ValueError('duplicate domain')
                seen_domains.add(domain)
            home = urlsplit(row['home_url']).hostname
            if not any(home == d or home.endswith('.' + d) for d in row['domains']):
                raise ValueError('home URL must belong to a declared domain')
            _rule(row)
            for field in ('actions_per_hour', 'actions_per_day'):
                if type(row[field]) is not int or row[field] <= 0:
                    raise ValueError('budgets must be positive integers')
        except (ValueError, TypeError, KeyError) as exc:
            raise RegistryError(f'Invalid browser platform {name!r}: {exc}') from exc
    try:
        extras = data.get('extra_rules', [])
        if not isinstance(extras, list):
            raise ValueError('extra_rules must be a list')
        for rule in extras:
            if not isinstance(rule, dict) or set(rule) != {'suffix', 'label', 'min_seconds_between_actions', 'unattended', 'refuse', 'confirm', 'note'}:
                raise ValueError('invalid extra rule fields')
            if not isinstance(rule['label'], str) or not rule['label'].strip() or not isinstance(rule['note'], str):
                raise ValueError('extra rules need a text label and note')
            _host(rule['suffix'])
            if rule['suffix'] in seen_domains:
                raise ValueError('duplicate extra rule domain')
            seen_domains.add(rule['suffix'])
            _rule(rule)
        aliases = data.get('budget_aliases', {})
        budgets = data.get('extra_budgets', {})
        if not isinstance(aliases, dict) or not isinstance(budgets, dict):
            raise ValueError('budget aliases and extra budgets must be mappings')
        if any(not isinstance(target, str) or target not in seen_ids or alias in seen_ids for alias, target in aliases.items()):
            raise ValueError('invalid budget alias')
        for name, limits in budgets.items():
            if name in seen_ids or not isinstance(limits, list) or len(limits) != 2 or any(type(v) is not int or v <= 0 for v in limits):
                raise ValueError('invalid extra budget')
    except (ValueError, TypeError, KeyError) as exc:
        raise RegistryError(f'Invalid browser registry: {exc}') from exc
    return data
