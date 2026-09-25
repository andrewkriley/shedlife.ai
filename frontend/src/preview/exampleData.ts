export const ONBOARDING_STEPS = [
  'Proxmox host',
  'Token ID',
  'Token Secret',
  'Network & storage',
  'AI provider',
  'Tenant',
  'Install mode',
  'Summary',
] as const

export const PROVIDERS = [
  { id: 'anthropic', label: 'Anthropic' },
  { id: 'openai', label: 'OpenAI' },
  { id: 'gemini', label: 'Gemini' },
] as const

export const READONLY_PROBES = [
  'llm_key',
  'outbound_https',
  'proxmox_api',
  'proxmox_capacity',
  'bridge_exists',
  'storage_pool_exists',
  'ntp_ok',
  'adopted_endpoint',
  'domain_resolves',
] as const

export const CHAT_SUGGESTIONS = [
  'Validate these foundations',
  'Run the pre-deploy probes',
  'Install the SSH key',
  'Export the YAML bundle',
] as const

export type ProbeStatus = 'pass' | 'fail' | 'not run'

export type PreviewIssue = {
  id: string
  classification: 'unexpected' | 'operator'
  summary: string
}

export type PreviewFoundations = {
  tenant: { name: string; slug: string }
  proxmox: { host: string; node: string; tokenId: string; tokenSet: boolean }
  network: { bridge: string; address: string; gateway: string }
  storage: { pool: string }
  provider: { vendor: string; keySet: boolean }
  intent: {
    mode: 'build' | 'adopt'
    gitlabUrl: string
    infisicalUrl: string
    dnsUrl: string
    k3sUrl: string
  }
  probes: Record<string, ProbeStatus>
}

export type PreviewDiscovery = {
  nodes: string[]
  bridges: string[]
  pools: string[]
  networks: Record<string, { address: string; gateway: string }>
}

export type PreviewCheck = {
  id: string
  label: string
  status: 'pass' | 'warn' | 'fail'
  detail: string
}

export function emptyFoundations(): PreviewFoundations {
  return {
    tenant: { name: '', slug: '' },
    proxmox: { host: '', node: '', tokenId: '', tokenSet: false },
    network: { bridge: '', address: '', gateway: '' },
    storage: { pool: '' },
    provider: { vendor: 'anthropic', keySet: false },
    intent: { mode: 'build', gitlabUrl: '', infisicalUrl: '', dnsUrl: '', k3sUrl: '' },
    probes: Object.fromEntries([...READONLY_PROBES, 'ssh_key_installed'].map((id) => [id, 'not run'])),
  }
}

export const EXAMPLE_DISCOVERY: PreviewDiscovery = {
  nodes: ['pve'],
  bridges: ['vmbr0', 'vmbr1'],
  pools: ['local-lvm', 'local'],
  networks: {
    vmbr0: { address: '192.0.2.10/24', gateway: '192.0.2.1' },
    vmbr1: { address: '10.0.0.2/24', gateway: '10.0.0.1' },
  },
}

export const SEEDED_ISSUE: PreviewIssue = {
  id: 'iss-preview-1',
  classification: 'unexpected',
  summary: 'predeploy-probe ntp_ok crashed while reading chrony',
}

export function summaryChecks(doc: PreviewFoundations): PreviewCheck[] {
  return [
    {
      id: 'proxmox',
      label: 'Proxmox API',
      status: doc.proxmox.host && doc.proxmox.tokenSet ? 'pass' : 'fail',
      detail: doc.proxmox.host || 'host missing',
    },
    {
      id: 'network',
      label: 'Network & storage',
      status: doc.network.bridge && doc.storage.pool ? 'pass' : 'fail',
      detail: `${doc.network.bridge || 'no bridge'} · ${doc.storage.pool || 'no pool'}`,
    },
    {
      id: 'provider',
      label: 'LLM provider',
      status: doc.provider.keySet ? 'pass' : 'fail',
      detail: doc.provider.vendor,
    },
    {
      id: 'tenant',
      label: 'Tenant',
      status: doc.tenant.name && doc.tenant.slug ? 'pass' : 'fail',
      detail: doc.tenant.slug || 'slug missing',
    },
    {
      id: 'intent',
      label: 'Install mode',
      status: 'pass',
      detail: doc.intent.mode === 'build' ? 'fresh install' : 'adopt existing services',
    },
  ]
}

export function foundationsYaml(doc: PreviewFoundations): string {
  return [
    'version: 1',
    'tenant:',
    `  name: ${doc.tenant.name}`,
    `  slug: ${doc.tenant.slug}`,
    'proxmox:',
    `  host: ${doc.proxmox.host}`,
    `  node: ${doc.proxmox.node}`,
    `  api_token_ref: local://proxmox/api_token`,
    'network:',
    `  bridge: ${doc.network.bridge}`,
    `  address: ${doc.network.address}`,
    `  gateway: ${doc.network.gateway}`,
    'storage:',
    `  pool: ${doc.storage.pool}`,
    'intent:',
    `  mode: ${doc.intent.mode}`,
  ].join('\n')
}
