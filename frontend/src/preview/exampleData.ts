export type PhaseId = 'prereq' | 'bootstrap' | 'deploy' | 'build'
export type FieldInput = 'text' | 'password' | 'textarea'

export type JourneyField = {
  id: string
  label: string
  input: FieldInput
  placeholder?: string
}

export type JourneyItemDef = {
  id: string
  phase: PhaseId
  title: string
  detail: string
  fields: JourneyField[]
  actionLabel?: string
}

export type ItemState = {
  values: Record<string, string>
  done: boolean
}

export type JourneyState = Record<string, ItemState>

export const PHASES: { id: PhaseId; title: string; lede: string }[] = [
  { id: 'prereq', title: 'Pre-req', lede: 'Facts the host already has.' },
  { id: 'bootstrap', title: 'Bootstrap', lede: 'The first container, then the checks.' },
  { id: 'deploy', title: 'Deploy', lede: 'Foundational platforms. Not MVP yet.' },
  { id: 'build', title: 'Build', lede: 'The lab tools. Not MVP yet.' },
]

export const JOURNEY_ITEMS: JourneyItemDef[] = [
  {
    id: 'proxmox-ip',
    phase: 'prereq',
    title: 'Proxmox IP',
    detail: 'The first host. An address or API URL is enough.',
    fields: [{ id: 'host', label: 'Address', input: 'text', placeholder: '192.0.2.10' }],
  },
  {
    id: 'proxmox-token-id',
    phase: 'prereq',
    title: 'Proxmox Token ID',
    detail: 'USER@REALM!tokenid. The secret is the next step.',
    fields: [
      { id: 'tokenId', label: 'Proxmox Token ID', input: 'text', placeholder: 'USER@REALM!tokenid' },
    ],
  },
  {
    id: 'proxmox-token-secret',
    phase: 'prereq',
    title: 'Proxmox Token Secret',
    detail: 'Stored locally. It is not shown again after you continue.',
    fields: [{ id: 'tokenSecret', label: 'Proxmox Token Secret', input: 'password' }],
  },
  {
    id: 'aws',
    phase: 'prereq',
    title: 'AWS',
    detail: 'Landing-zone credentials. Values stay in the browser for this preview.',
    fields: [
      { id: 'accessKey', label: 'Access key ID', input: 'text', placeholder: 'AKIA…' },
      { id: 'secretKey', label: 'Secret access key', input: 'password' },
    ],
  },
  {
    id: 'openrouter',
    phase: 'prereq',
    title: 'OpenRouter API',
    detail: 'The key chat will use. A Claude subscription will not work.',
    fields: [{ id: 'apiKey', label: 'OpenRouter API key', input: 'password' }],
  },
  {
    id: 'domain',
    phase: 'prereq',
    title: 'Domain name',
    detail: 'The name Deploy will aim services at.',
    fields: [{ id: 'domain', label: 'Domain name', input: 'text', placeholder: 'lab.example' }],
  },
  {
    id: 'ssh-key',
    phase: 'prereq',
    title: 'Trusted SSH key',
    detail: 'Your public key. Bootstrap will trust this one.',
    fields: [{ id: 'publicKey', label: 'Trusted SSH key', input: 'textarea', placeholder: 'ssh-ed25519 …' }],
  },
  {
    id: 'cloudflare',
    phase: 'prereq',
    title: 'Cloudflare API',
    detail: 'Token for DNS and the tunnel, when Deploy exists.',
    fields: [{ id: 'apiToken', label: 'Cloudflare API token', input: 'password' }],
  },
  {
    id: 'lxc',
    phase: 'bootstrap',
    title: 'LXC',
    detail: 'The bootstrap container. The installer already did this on a real host.',
    fields: [],
    actionLabel: 'Create LXC',
  },
  {
    id: 'validation',
    phase: 'bootstrap',
    title: 'Validation checks',
    detail: 'Confirms every prerequisite before Deploy can start.',
    fields: [],
    actionLabel: 'Run checks',
  },
  {
    id: 'gitlab',
    phase: 'deploy',
    title: 'GitLab',
    detail: 'Source of truth for the tenant Fleet, once Deploy is in scope.',
    fields: [],
    actionLabel: 'Provision GitLab',
  },
  {
    id: 'infisical',
    phase: 'deploy',
    title: 'Infisical · PKI, secrets',
    detail: 'PKI and secrets. Replaces local secret-zero.',
    fields: [],
    actionLabel: 'Provision Infisical',
  },
  {
    id: 'dns',
    phase: 'deploy',
    title: 'DNS',
    detail: 'Authoritative DNS for the domain you collected.',
    fields: [],
    actionLabel: 'Provision DNS',
  },
  {
    id: 'k3s',
    phase: 'deploy',
    title: 'K3S',
    detail: 'The first cluster. Playbook, not an invented layout.',
    fields: [],
    actionLabel: 'Provision K3S',
  },
  {
    id: 'aws-landing',
    phase: 'deploy',
    title: 'AWS landing zone',
    detail: 'The cloud side of the same tenant.',
    fields: [],
    actionLabel: 'Apply landing zone',
  },
  {
    id: 'proxmox-templates',
    phase: 'deploy',
    title: 'Proxmox templates',
    detail: 'Golden images the later playbooks clone from.',
    fields: [],
    actionLabel: 'Build templates',
  },
  {
    id: 'stepca',
    phase: 'deploy',
    title: 'StepCA',
    detail: 'Internal CA alongside Infisical PKI.',
    fields: [],
    actionLabel: 'Provision StepCA',
  },
  {
    id: 'proxmox-cluster',
    phase: 'build',
    title: 'Proxmox Cluster',
    detail: 'Three or five hosts. A later grill decides the shape.',
    fields: [],
    actionLabel: 'Form cluster',
  },
  {
    id: 'traefik',
    phase: 'build',
    title: 'Traefik',
    detail: 'Ingress for the lab.',
    fields: [],
    actionLabel: 'Deploy Traefik',
  },
  {
    id: 'gpu',
    phase: 'build',
    title: 'Local GPU · Ollama / vLLM',
    detail: 'Ollama or vLLM on the local GPUs.',
    fields: [],
    actionLabel: 'Start GPU runtime',
  },
  {
    id: 'litellm',
    phase: 'build',
    title: 'LiteLLM gateway',
    detail: 'One door for local and cloud models.',
    fields: [],
    actionLabel: 'Deploy LiteLLM',
  },
]

export function emptyJourney(): JourneyState {
  return Object.fromEntries(
    JOURNEY_ITEMS.map((item) => [
      item.id,
      {
        values: Object.fromEntries(item.fields.map((field) => [field.id, ''])),
        done: false,
      },
    ]),
  )
}

export function itemsForPhase(phase: PhaseId): JourneyItemDef[] {
  return JOURNEY_ITEMS.filter((item) => item.phase === phase)
}

export function itemById(id: string): JourneyItemDef | undefined {
  return JOURNEY_ITEMS.find((item) => item.id === id)
}

export function fieldsFilled(item: JourneyItemDef, state: ItemState | undefined): boolean {
  if (!item.fields.length) return Boolean(state?.done)
  return item.fields.every((field) => Boolean(state?.values[field.id]?.trim()) || state?.done)
}

export function phaseProgress(phase: PhaseId, state: JourneyState): { done: number; total: number } {
  const items = itemsForPhase(phase)
  const done = items.filter((item) => state[item.id]?.done).length
  return { done, total: items.length }
}

export function overallProgress(state: JourneyState): { done: number; total: number } {
  const done = JOURNEY_ITEMS.filter((item) => state[item.id]?.done).length
  return { done, total: JOURNEY_ITEMS.length }
}

export function prereqReady(state: JourneyState): boolean {
  return itemsForPhase('prereq').every((item) => state[item.id]?.done)
}

export function joinTitles(phase: PhaseId): string {
  const titles = itemsForPhase(phase).map((item) => item.title)
  if (titles.length <= 1) return titles[0] ?? ''
  return `${titles.slice(0, -1).join(', ')}, and ${titles[titles.length - 1]}`
}

export function prereqSummary(state: JourneyState): string {
  const host = state['proxmox-ip']?.values.host?.trim() || 'the first host'
  const domain = state['domain']?.values.domain?.trim() || 'the domain'
  return `Proxmox is ${host}. Services will aim at ${domain}. Tokens, keys, and the SSH trust are saved locally.`
}

export function rowDetail(item: JourneyItemDef, state: ItemState | undefined): string {
  if (item.fields.some((field) => field.input === 'password' || field.input === 'textarea')) {
    return fieldsFilled(item, state) ? 'Saved' : 'Not set'
  }
  if (item.fields.length === 1) {
    const value = state?.values[item.fields[0].id]?.trim()
    return value || 'Not set'
  }
  if (item.fields.length > 1) {
    return fieldsFilled(item, state) ? 'Saved' : 'Not set'
  }
  return state?.done ? 'Ready' : 'Not run'
}

export function journeyYaml(state: JourneyState): string {
  const host = state['proxmox-ip']?.values.host ?? ''
  const domain = state['domain']?.values.domain ?? ''
  return [
    'version: 1',
    'prereq:',
    `  proxmox_host: ${host}`,
    '  proxmox_token_ref: local://proxmox/api_token',
    '  aws_ref: local://aws/credentials',
    '  openrouter_ref: local://providers/openrouter/api_key',
    `  domain: ${domain}`,
    '  ssh_key_ref: local://operator/ssh_public_key',
    '  cloudflare_ref: local://cloudflare/api_token',
    'bootstrap:',
    `  lxc: ${state.lxc?.done ? 'ready' : 'pending'}`,
    `  validation: ${state.validation?.done ? 'ready' : 'pending'}`,
  ].join('\n')
}
