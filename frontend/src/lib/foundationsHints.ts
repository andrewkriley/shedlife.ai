/** Hover copy for every foundations field. Source: docs/prd/bootstrap.md. */

export const FOUNDATION_HINTS = {
  'tenant.name':
    'Display name for this tenant. Shown in the UI. Not a hostname and not shedlife.ai.',
  'tenant.slug':
    'Short id used in later platform names. Lowercase letters, digits, and hyphens only ([a-z0-9-]+).',
  'operator.email':
    'Contact identity for this tenant. The login password is not stored on this schema.',
  'proxmox.host':
    'API URL or address of the first Proxmox host. Intake jobs authenticate against this host.',
  'proxmox.node':
    'Node name if more than one node is already there (intent only). Cluster formation is a later phase.',
  'proxmox.api_token_id':
    'Proxmox Token ID, like USER@REALM!tokenid. Combined with the secret when saved; never exported.',
  'proxmox.api_token_secret':
    'Proxmox Token Secret. Stored only in local secrets, never in YAML, logs, or the export bundle.',
  'network.bridge':
    'LAN bridge this CT and later VMs attach to, usually vmbr0 on a single host.',
  'network.address':
    'Operator-facing address as CIDR (address/prefix) for later platform NICs. Filled from the chosen Proxmox bridge when discovered.',
  'network.gateway':
    'Gateway IP for that address. Filled from the chosen Proxmox bridge when discovered.',
  'network.ntp':
    'Time source. inherit uses the Proxmox host clock/NTP. Or list explicit NTP servers.',
  'storage.pool':
    'Storage pool name for later VM disks. Single-host only this phase.',
  'domains.intended':
    'Hostnames for later ingress, comma-separated. They may not resolve yet. Use workshop-device labels (scope, bench, solder), never server01 or web.',
  'intent.mode.build':
    'Build: Deploy will create this later. Nothing is contacted now except as a probe.',
  'intent.mode.adopt':
    'Adopt: use an existing install. Collect its URL; only a shallow reachability probe runs.',
  'intent.mode.dns':
    'Greenfield: Deploy will create DNS later. Brownfield: use an existing DNS endpoint (URL required).',
  'intent.url':
    'URL of the existing platform. Required when mode is adopt or brownfield. Probed for reachability only.',
  'proxmox.ssh_key_fingerprint':
    'Fingerprint of the dedicated SSH key after ssh_key_installed succeeds. Empty until that probe is approved in chat.',
} as const

export type FoundationHintKey = keyof typeof FOUNDATION_HINTS
