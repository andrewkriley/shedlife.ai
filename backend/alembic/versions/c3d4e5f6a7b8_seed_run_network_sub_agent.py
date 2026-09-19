"""seed run.network sub-agent

Revision ID: c3d4e5f6a7b8
Revises: 2b1bb177b154
Create Date: 2026-09-19 13:00:00.000000

The second real sub-agent, per docs/prd/core-agentic-loop.md ("The three
real sub-agents this phase" -- run.network via the existing unifi-mcp MCP
server, already a standing network service). `tools` is a snapshot of what
unifi-mcp actually returned from a live list_tools() call, not hand-typed --
input_schema is each tool's real JSON Schema (with the SDK's own `$schema`
meta key stripped, since Anthropic's tool spec doesn't expect it).
has_side_effects follows unifi-mcp's own preview_*/confirm_* naming
convention directly: a confirm_* tool applies a change for real and is
flagged true; everything else (list_*/get_*/preview_*) only reads or
previews, never mutates, and is flagged false.
"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = '2b1bb177b154'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SUB_AGENTS_TABLE = sa.table(
    "sub_agents",
    sa.column("id", sa.String),
    sa.column("macro_category", sa.String),
    sa.column("description", sa.String),
    sa.column("system_prompt", sa.String),
    sa.column("tools", postgresql.JSON),
    sa.column("default_provider", sa.String),
    sa.column("default_model", sa.String),
    sa.column("provenance", sa.String),
    sa.column("created_at", sa.DateTime(timezone=True)),
)

RUN_NETWORK_SYSTEM_PROMPT = """\
You are The Shed's network operations agent, managing this home network through \
UniFi. You can directly inspect sites, devices, clients, networks, firewall zones, \
firewall policies, and DHCP leases with the list_*/get_* tools -- use exact IDs from \
those results rather than guessing them.

Any change (creating, updating, or deleting a network, firewall zone, or firewall \
policy; setting a client's alias or fixed IP; updating a network's DHCP DNS servers) \
is a two-step preview/confirm pair: call the matching preview_* tool first to get a \
preview_token, then call the matching confirm_* tool with that token to actually \
apply it. The confirm_* call will pause for explicit human approval before it runs -- \
explain what you're about to change and why before calling it, so that approval is \
meaningful."""

RUN_NETWORK_TOOLS = [{'name': 'list_sites',
  'description': 'List all UniFi sites managed by this controller',
  'input_schema': {'type': 'object', 'properties': {}},
  'has_side_effects': False},
 {'name': 'list_networks',
  'description': 'List all networks (VLANs / LANs) on the configured site',
  'input_schema': {'type': 'object', 'properties': {}},
  'has_side_effects': False},
 {'name': 'list_clients',
  'description': 'List all clients (wired + wireless) currently visible to the controller',
  'input_schema': {'type': 'object', 'properties': {}},
  'has_side_effects': False},
 {'name': 'list_devices',
  'description': 'List all UniFi devices (APs / switches / gateways) adopted on this site',
  'input_schema': {'type': 'object', 'properties': {}},
  'has_side_effects': False},
 {'name': 'get_dhcp_leases',
  'description': 'Get the list of active DHCP leases',
  'input_schema': {'type': 'object', 'properties': {}},
  'has_side_effects': False},
 {'name': 'list_firewall_zones',
  'description': 'List Zone-Based Firewall zones and their member networks/VLANs (read-only)',
  'input_schema': {'type': 'object', 'properties': {}},
  'has_side_effects': False},
 {'name': 'list_firewall_policies',
  'description': 'List Zone-Based Firewall policies (the zone-to-zone allow/block/reject matrix '
                 'and per-policy rules; read-only)',
  'input_schema': {'type': 'object', 'properties': {}},
  'has_side_effects': False},
 {'name': 'preview_set_client_alias',
  'description': 'Preview a client alias change. Returns a preview_token; pass to '
                 'confirm_set_client_alias to execute.',
  'input_schema': {'type': 'object',
                   'properties': {'client_id': {'type': 'string',
                                                'description': 'Client UUID from list_clients'},
                                  'new_alias': {'type': 'string',
                                                'description': 'Friendly display name to assign'}},
                   'required': ['client_id', 'new_alias'],
                   'additionalProperties': False},
  'has_side_effects': False},
 {'name': 'preview_set_client_fixed_ip',
  'description': 'Preview assignment of a fixed (reserved) IP to a client. Returns a '
                 'preview_token.',
  'input_schema': {'type': 'object',
                   'properties': {'client_id': {'type': 'string',
                                                'description': 'Client UUID from list_clients'},
                                  'fixed_ip': {'type': 'string',
                                               'description': 'IPv4 address to reserve for this '
                                                              'client'}},
                   'required': ['client_id', 'fixed_ip'],
                   'additionalProperties': False},
  'has_side_effects': False},
 {'name': 'preview_update_dhcp_dns_servers',
  'description': "Preview an update to a network's DHCP-handed DNS server list. Returns a "
                 'preview_token.',
  'input_schema': {'type': 'object',
                   'properties': {'network_id': {'type': 'string',
                                                 'description': 'Network UUID from list_networks'},
                                  'dns_servers': {'type': 'array',
                                                  'items': {'type': 'string'},
                                                  'minItems': 1,
                                                  'maxItems': 4,
                                                  'description': 'Up to 4 IPv4 addresses to '
                                                                 'advertise via DHCP option 6'}},
                   'required': ['network_id', 'dns_servers'],
                   'additionalProperties': False},
  'has_side_effects': False},
 {'name': 'preview_create_network',
  'description': 'Preview creation of a new network (VLAN/LAN). Returns a preview_token.',
  'input_schema': {'type': 'object',
                   'properties': {'network': {'type': 'object',
                                              'additionalProperties': {},
                                              'description': 'UniFi network object (see UniFi API '
                                                             'docs). Required fields: name, '
                                                             "purpose (e.g. 'corporate'), vlan, "
                                                             'subnet (CIDR).'}},
                   'required': ['network'],
                   'additionalProperties': False},
  'has_side_effects': False},
 {'name': 'preview_delete_network',
  'description': 'Preview deletion of a network. Returns a preview_token.',
  'input_schema': {'type': 'object',
                   'properties': {'network_id': {'type': 'string',
                                                 'description': 'Network UUID from list_networks'}},
                   'required': ['network_id'],
                   'additionalProperties': False},
  'has_side_effects': False},
 {'name': 'confirm_set_client_alias',
  'description': 'Execute a previously previewed client alias change.',
  'input_schema': {'type': 'object',
                   'properties': {'preview_token': {'type': 'string'}},
                   'required': ['preview_token'],
                   'additionalProperties': False},
  'has_side_effects': True},
 {'name': 'confirm_set_client_fixed_ip',
  'description': 'Execute a previously previewed fixed-IP assignment.',
  'input_schema': {'type': 'object',
                   'properties': {'preview_token': {'type': 'string'}},
                   'required': ['preview_token'],
                   'additionalProperties': False},
  'has_side_effects': True},
 {'name': 'confirm_update_dhcp_dns_servers',
  'description': 'Execute a previously previewed DHCP DNS server list update.',
  'input_schema': {'type': 'object',
                   'properties': {'preview_token': {'type': 'string'}},
                   'required': ['preview_token'],
                   'additionalProperties': False},
  'has_side_effects': True},
 {'name': 'confirm_create_network',
  'description': 'Execute a previously previewed network creation.',
  'input_schema': {'type': 'object',
                   'properties': {'preview_token': {'type': 'string'}},
                   'required': ['preview_token'],
                   'additionalProperties': False},
  'has_side_effects': True},
 {'name': 'confirm_delete_network',
  'description': 'Execute a previously previewed network deletion.',
  'input_schema': {'type': 'object',
                   'properties': {'preview_token': {'type': 'string'}},
                   'required': ['preview_token'],
                   'additionalProperties': False},
  'has_side_effects': True},
 {'name': 'preview_create_firewall_policy',
  'description': 'Preview creation of a Zone-Based Firewall policy. Refuses lockout-risky rules. '
                 'Returns a preview_token.',
  'input_schema': {'type': 'object',
                   'properties': {'policy': {'type': 'object',
                                             'additionalProperties': {},
                                             'description': 'UniFi ZBF policy object: name, '
                                                            'enabled, '
                                                            'action{type:ALLOW|BLOCK|REJECT}, '
                                                            'source{zoneId,…}, '
                                                            'destination{zoneId,…}, '
                                                            'ipProtocolScope{ipVersion}, '
                                                            'loggingEnabled. Get zoneIds from '
                                                            'list_firewall_zones.'}},
                   'required': ['policy'],
                   'additionalProperties': False},
  'has_side_effects': False},
 {'name': 'confirm_create_firewall_policy',
  'description': 'Execute a previously previewed firewall-policy creation (with auto-rollback).',
  'input_schema': {'type': 'object',
                   'properties': {'preview_token': {'type': 'string'}},
                   'required': ['preview_token'],
                   'additionalProperties': False},
  'has_side_effects': True},
 {'name': 'preview_update_firewall_policy',
  'description': 'Preview an update (PATCH) to a firewall policy. Refuses disabling/blocking an '
                 'admin path. Returns a preview_token.',
  'input_schema': {'type': 'object',
                   'properties': {'policy_id': {'type': 'string',
                                                'description': 'Policy UUID from '
                                                               'list_firewall_policies'},
                                  'patch': {'type': 'object',
                                            'additionalProperties': {},
                                            'description': 'Fields to change, e.g. {enabled:false} '
                                                           "or {action:{type:'BLOCK'}}"}},
                   'required': ['policy_id', 'patch'],
                   'additionalProperties': False},
  'has_side_effects': False},
 {'name': 'confirm_update_firewall_policy',
  'description': 'Execute a previously previewed firewall-policy update (with auto-rollback).',
  'input_schema': {'type': 'object',
                   'properties': {'preview_token': {'type': 'string'}},
                   'required': ['preview_token'],
                   'additionalProperties': False},
  'has_side_effects': True},
 {'name': 'preview_delete_firewall_policy',
  'description': 'Preview deletion of a firewall policy. Refuses deleting SYSTEM_DEFINED or '
                 'admin-path policies. Returns a preview_token.',
  'input_schema': {'type': 'object',
                   'properties': {'policy_id': {'type': 'string',
                                                'description': 'Policy UUID from '
                                                               'list_firewall_policies'}},
                   'required': ['policy_id'],
                   'additionalProperties': False},
  'has_side_effects': False},
 {'name': 'confirm_delete_firewall_policy',
  'description': 'Execute a previously previewed firewall-policy deletion (with auto-rollback).',
  'input_schema': {'type': 'object',
                   'properties': {'preview_token': {'type': 'string'}},
                   'required': ['preview_token'],
                   'additionalProperties': False},
  'has_side_effects': True},
 {'name': 'preview_create_firewall_zone',
  'description': 'Preview creation of a firewall zone. Returns a preview_token.',
  'input_schema': {'type': 'object',
                   'properties': {'zone': {'type': 'object',
                                           'additionalProperties': {},
                                           'description': 'Zone object: name (required), '
                                                          'networkIds (array of network UUIDs from '
                                                          'list_networks).'}},
                   'required': ['zone'],
                   'additionalProperties': False},
  'has_side_effects': False},
 {'name': 'confirm_create_firewall_zone',
  'description': 'Execute a previously previewed firewall-zone creation (with auto-rollback).',
  'input_schema': {'type': 'object',
                   'properties': {'preview_token': {'type': 'string'}},
                   'required': ['preview_token'],
                   'additionalProperties': False},
  'has_side_effects': True},
 {'name': 'preview_update_firewall_zone',
  'description': 'Preview an update (PUT, full replace) to a firewall zone. Refuses '
                 'non-configurable system zones. Returns a preview_token.',
  'input_schema': {'type': 'object',
                   'properties': {'zone_id': {'type': 'string',
                                              'description': 'Zone UUID from list_firewall_zones'},
                                  'zone': {'type': 'object',
                                           'additionalProperties': {},
                                           'description': 'Full zone object (PUT replaces): name, '
                                                          'networkIds.'}},
                   'required': ['zone_id', 'zone'],
                   'additionalProperties': False},
  'has_side_effects': False},
 {'name': 'confirm_update_firewall_zone',
  'description': 'Execute a previously previewed firewall-zone update (with auto-rollback).',
  'input_schema': {'type': 'object',
                   'properties': {'preview_token': {'type': 'string'}},
                   'required': ['preview_token'],
                   'additionalProperties': False},
  'has_side_effects': True},
 {'name': 'preview_delete_firewall_zone',
  'description': 'Preview deletion of a firewall zone. Refuses SYSTEM_DEFINED zones or zones with '
                 'member networks. Returns a preview_token.',
  'input_schema': {'type': 'object',
                   'properties': {'zone_id': {'type': 'string',
                                              'description': 'Zone UUID from list_firewall_zones'}},
                   'required': ['zone_id'],
                   'additionalProperties': False},
  'has_side_effects': False},
 {'name': 'confirm_delete_firewall_zone',
  'description': 'Execute a previously previewed firewall-zone deletion (with auto-rollback).',
  'input_schema': {'type': 'object',
                   'properties': {'preview_token': {'type': 'string'}},
                   'required': ['preview_token'],
                   'additionalProperties': False},
  'has_side_effects': True}]


def upgrade() -> None:
    op.bulk_insert(
        SUB_AGENTS_TABLE,
        [
            {
                "id": "run.network",
                "macro_category": "run",
                "description": (
                    "Manages this home network via UniFi: sites, devices, clients, networks, "
                    "firewall zones/policies, and DHCP leases. Can make real changes (network, "
                    "firewall, client, and DHCP config), each requiring explicit approval."
                ),
                "system_prompt": RUN_NETWORK_SYSTEM_PROMPT,
                "tools": RUN_NETWORK_TOOLS,
                "default_provider": "anthropic",
                "default_model": "claude-sonnet-5",
                "provenance": "manual",
                "created_at": datetime.now(timezone.utc),
            }
        ],
    )


def downgrade() -> None:
    op.execute(SUB_AGENTS_TABLE.delete().where(SUB_AGENTS_TABLE.c.id == "run.network"))
