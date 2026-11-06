"""Read-only validation of explicit legacy CRM ownership decisions.

This does not migrate or enable tenancy. An apply operation must additionally
archive, reconcile, quarantine unassigned data and enforce every runtime path.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Mapping

from .schema import CRM_TABLES, SCHEMA_SQL

_WORKSPACE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
_INSTALL = '__install__'
# Every table requires an explicit review when the production schema grows.
_REVIEWED = frozenset('''contacts campaigns campaign_contacts drafts messages campaign_events
email_templates expert_chunks idempotency_records memory_items provider_calls discovery_runs
discovery_candidates research_entities research_edges research_observations sales_leads
sales_setter_activity sales_monthly_goals sales_lead_events ai_chat_projects ai_chats ai_messages
email_sending_identities email_campaign_settings email_contact_permissions email_suppressions
email_unsubscribe_tokens email_send_jobs email_rate_state email_delivery_events campaign_reply_triage
campaign_followup_tasks campaign_sales_links'''.split())


class OwnershipError(ValueError):
    """A fixed, content-free refusal; never echo customer fields or identifiers."""


@dataclass(frozen=True)
class OwnershipPlan:
    assignments: Mapping[tuple[str, tuple[str, ...]], str]
    source_sha256: str
    counts: Mapping[str, int]

    def owner(self, table: str, key: tuple[str, ...]) -> str:
        return self.assignments[(table, key)]


@lru_cache(maxsize=1)
def _layout():
    if set(CRM_TABLES) != _REVIEWED:
        raise OwnershipError('CRM schema changed; review every table before ownership migration')
    connection = sqlite3.connect(':memory:')
    try:
        connection.executescript(SCHEMA_SQL)
        result = {}
        for table in CRM_TABLES:
            columns = connection.execute(f'PRAGMA table_info({table})').fetchall()
            keys = tuple(row[1] for row in sorted(columns, key=lambda row: row[5]) if row[5])
            required = {row[1] for row in columns if row[3]}
            links = tuple((row[3], row[2], row[4], row[3] in required)
                          for row in connection.execute(f'PRAGMA foreign_key_list({table})'))
            result[table] = (keys, links)
        return result
    finally:
        connection.close()


def _key(row, columns):
    values = tuple(row.get(column) for column in columns)
    if any(not isinstance(value, str) or not value or len(value) > 1000 for value in values):
        raise OwnershipError('A CRM primary key is invalid; preserve the source')
    return values


def validate_ownership(rows: dict[str, list[dict[str, Any]]], manifest: dict[str, Any], *, workspaces: set[str]) -> OwnershipPlan:
    """Require a complete decision for unowned roots and consistent references."""
    if not isinstance(manifest, dict) or set(manifest) != {'version', 'assignments'}:
        raise OwnershipError('Use the versioned ownership manifest without default assignments')
    if type(manifest['version']) is not int or manifest['version'] != 1 or not isinstance(manifest['assignments'], dict):
        raise OwnershipError('Ownership manifest version or assignments are invalid')
    if not isinstance(workspaces, (set, frozenset)) or not workspaces or any(not isinstance(value, str) or not _WORKSPACE.fullmatch(value) for value in workspaces):
        raise OwnershipError('Use existing validated workspace identifiers')
    layout = _layout()
    if not isinstance(rows, dict) or set(rows) - set(layout):
        raise OwnershipError('CRM snapshot contains an unreviewed table')
    indexed = {}
    for table, records in rows.items():
        if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
            raise OwnershipError('CRM snapshot rows are invalid')
        for row in records:
            identifier = (table, _key(row, layout[table][0]))
            if identifier in indexed:
                raise OwnershipError('CRM snapshot contains duplicate primary keys')
            indexed[identifier] = row
    explicit = {}
    for table, decisions in manifest['assignments'].items():
        if table not in layout or not isinstance(decisions, list):
            raise OwnershipError('Ownership manifest names an unreviewed table')
        for decision in decisions:
            if not isinstance(decision, dict) or set(decision) != {'key', 'workspace_id'} or not isinstance(decision['key'], list):
                raise OwnershipError('Ownership assignment fields are invalid')
            columns = layout[table][0]
            if len(decision['key']) != len(columns):
                raise OwnershipError('Ownership assignment primary key is invalid')
            key = _key(dict(zip(columns, decision['key'])), columns)
            identifier = (table, key)
            if identifier not in indexed or identifier in explicit:
                raise OwnershipError('Ownership assignment is unknown or duplicated')
            workspace = decision['workspace_id']
            # Reputation protections and shared account rate counters remain
            # install-wide only when the operator explicitly classifies them.
            if table == 'email_suppressions' and workspace == _INSTALL and indexed[identifier].get('reason') not in {'hard_bounce', 'complaint'}:
                raise OwnershipError('Only reviewed reputation suppression can have install-wide scope')
            global_allowed = table in {'email_suppressions', 'email_rate_state'} and workspace == _INSTALL
            if not isinstance(workspace, str) or (workspace not in workspaces and not global_allowed):
                raise OwnershipError('Ownership assignment names an unknown workspace')
            if table == 'email_suppressions' and indexed[identifier].get('reason') in {'hard_bounce', 'complaint'} and workspace != _INSTALL:
                raise OwnershipError('Reputation suppression must retain explicit install-wide protection')
            explicit[identifier] = workspace
    owners = {}
    visiting = set()

    def resolve(identifier):
        if identifier in owners:
            return owners[identifier]
        if identifier in visiting:
            raise OwnershipError('Ownership graph contains an unresolved cycle')
        visiting.add(identifier)
        table, key = identifier
        row = indexed[identifier]
        recorded = row.get('workspace_id')
        chosen = explicit.get(identifier)
        if recorded:
            if not isinstance(recorded, str) or recorded not in workspaces:
                raise OwnershipError('A recorded owner is not an existing workspace')
            if chosen is not None and chosen != recorded:
                raise OwnershipError('An explicit assignment conflicts with a recorded owner')
            chosen = recorded
        parents = []
        for column, parent_table, parent_column, required in layout[table][1]:
            value = row.get(column)
            if value is None:
                if required:
                    raise OwnershipError('A required reference is missing; preserve the source')
                continue
            if value == '':
                raise OwnershipError('A required reference is empty; preserve the source')
            parent_keys = layout[parent_table][0]
            if parent_keys != (parent_column,):
                raise OwnershipError('A composite ownership reference needs explicit review')
            parent_id = (parent_table, (value,))
            if parent_id not in indexed:
                raise OwnershipError('CRM contains a missing referenced record')
            parents.append(resolve(parent_id))
        # Historical template provenance may outlive deletion of a template.
        # A still-existing template must belong to the same workspace.
        if table in {'drafts', 'messages'} and row.get('template_id'):
            template_id = ('email_templates', (row['template_id'],))
            if template_id in indexed:
                parents.append(resolve(template_id))
        if chosen is None:
            if not parents:
                raise OwnershipError('Every unowned root needs an explicit ownership assignment')
            chosen = parents[0]
        if any(owner != chosen for owner in parents):
            raise OwnershipError('A CRM reference crosses workspace ownership; resolve it explicitly')
        owners[identifier] = chosen
        visiting.remove(identifier)
        return chosen

    for identifier in indexed:
        resolve(identifier)
    # Ordinary foreign keys prove row existence, not that a membership belongs
    # to the same campaign as a task/event/job carrying both identifiers.
    for (table, key), row in indexed.items():
        if row.get('campaign_id') and row.get('campaign_contact_id'):
            membership = indexed.get(('campaign_contacts', (row['campaign_contact_id'],)))
            if membership is not None and membership.get('campaign_id') != row['campaign_id']:
                raise OwnershipError('A CRM membership belongs to a different campaign')
        if table in {'email_send_jobs', 'messages'} and row.get('draft_id'):
            draft = indexed.get(('drafts', (row['draft_id'],)))
            if draft is not None and draft.get('campaign_contact_id') != row.get('campaign_contact_id'):
                raise OwnershipError('A delivery record belongs to a different draft membership')
        if table == 'research_observations' and row.get('candidate_id') and row.get('run_id'):
            candidate = indexed.get(('discovery_candidates', (row['candidate_id'],)))
            if candidate is not None and candidate.get('run_id') != row['run_id']:
                raise OwnershipError('Research evidence belongs to a different discovery run')
    canonical = {table: sorted(records, key=lambda row: _key(row, layout[table][0])) for table, records in sorted(rows.items())}
    encoded = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return OwnershipPlan(MappingProxyType(owners), hashlib.sha256(encoded.encode()).hexdigest(),
                         MappingProxyType({table: len(records) for table, records in rows.items()}))


def capture_legacy_snapshot(store) -> dict[str, list[dict[str, Any]]]:
    """Read one consistent source; caller must hold the install migration lease."""
    _layout()
    with store.transaction():
        if store.backend == 'postgres':
            store.connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        return {table: [dict(row) for row in store.connection.execute(f'SELECT * FROM {table}').fetchall()]
                for table in CRM_TABLES}
