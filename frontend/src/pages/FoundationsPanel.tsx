import { useEffect, useState } from 'react'
import {
  exportFoundations,
  getFoundations,
  putFoundations,
  runProbe,
  validateFoundations,
  type FoundationsDocument,
} from '../lib/api'

const READONLY_PROBES = [
  'llm_key',
  'outbound_https',
  'proxmox_api',
  'proxmox_capacity',
  'bridge_exists',
  'storage_pool_exists',
  'ntp_ok',
  'adopted_endpoint',
  'domain_resolves',
]

const INTENT_KEYS = ['gitlab', 'infisical', 'dns', 'k3s'] as const

function emptyDoc(): FoundationsDocument {
  return {
    version: 1,
    tenant: { name: '', slug: '' },
    operator: { email: '' },
    proxmox: { host: '', node: '', ssh_key_fingerprint: null },
    network: { bridge: '', address: '', gateway: '', ntp: 'inherit' },
    storage: { pool: '' },
    domains: { intended: [] },
    intent: {
      gitlab: { mode: 'build' },
      infisical: { mode: 'build' },
      dns: { mode: 'greenfield' },
      k3s: { mode: 'build' },
    },
    probes: {},
  }
}

export function FoundationsPanel() {
  const [doc, setDoc] = useState<FoundationsDocument>(emptyDoc)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [status, setStatus] = useState<string | null>(null)

  async function refresh() {
    const next = await getFoundations()
    setDoc({ ...emptyDoc(), ...next, probes: next.probes ?? {} })
  }

  useEffect(() => {
    refresh().catch(() => setStatus('Failed to load foundations.'))
  }, [])

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setStatus(null)
    try {
      const saved = await putFoundations(doc)
      setDoc({ ...emptyDoc(), ...saved, probes: saved.probes ?? {} })
      setStatus('Saved.')
    } catch {
      setStatus('Failed to save foundations.')
    }
  }

  async function handleValidate() {
    setStatus(null)
    try {
      const result = await validateFoundations()
      setErrors(result.errors)
      setStatus(result.ok ? 'Valid.' : 'Field errors — not issues.')
    } catch {
      setStatus('Failed to validate.')
    }
  }

  async function handleExport() {
    setStatus(null)
    try {
      const yaml = await exportFoundations()
      const blob = new Blob([yaml], { type: 'text/yaml' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'foundations.yaml'
      link.click()
      URL.revokeObjectURL(url)
      setStatus('Exported.')
    } catch {
      setStatus('Failed to export.')
    }
  }

  async function handleProbe(id: string) {
    setStatus(null)
    try {
      const result = await runProbe(id)
      await refresh()
      setStatus(`${id}: ${result.status}`)
    } catch {
      setStatus(`Failed to run ${id}.`)
    }
  }

  return (
    <section className="panel" aria-label="foundations">
      <h2>Foundations</h2>
      <form onSubmit={handleSave}>
        <label htmlFor="tenant-name">Tenant name</label>
        <input
          id="tenant-name"
          value={doc.tenant.name}
          onChange={(e) => setDoc({ ...doc, tenant: { ...doc.tenant, name: e.target.value } })}
        />
        {errors['tenant.name'] && <p className="field-error">{errors['tenant.name']}</p>}

        <label htmlFor="tenant-slug">Tenant slug</label>
        <input
          id="tenant-slug"
          value={doc.tenant.slug}
          onChange={(e) => setDoc({ ...doc, tenant: { ...doc.tenant, slug: e.target.value } })}
        />
        {errors['tenant.slug'] && <p className="field-error">{errors['tenant.slug']}</p>}

        <label htmlFor="operator-email">Operator email</label>
        <input
          id="operator-email"
          type="email"
          value={doc.operator.email}
          onChange={(e) => setDoc({ ...doc, operator: { email: e.target.value } })}
        />
        {errors['operator.email'] && <p className="field-error">{errors['operator.email']}</p>}

        <label htmlFor="proxmox-host">Proxmox host</label>
        <input
          id="proxmox-host"
          value={doc.proxmox.host}
          onChange={(e) => setDoc({ ...doc, proxmox: { ...doc.proxmox, host: e.target.value } })}
        />

        <label htmlFor="proxmox-node">Proxmox node</label>
        <input
          id="proxmox-node"
          value={doc.proxmox.node}
          onChange={(e) => setDoc({ ...doc, proxmox: { ...doc.proxmox, node: e.target.value } })}
        />

        <label htmlFor="network-bridge">Bridge</label>
        <input
          id="network-bridge"
          value={doc.network.bridge}
          onChange={(e) => setDoc({ ...doc, network: { ...doc.network, bridge: e.target.value } })}
        />

        <label htmlFor="network-address">Address (CIDR)</label>
        <input
          id="network-address"
          value={doc.network.address}
          onChange={(e) => setDoc({ ...doc, network: { ...doc.network, address: e.target.value } })}
        />
        {errors['network.address'] && <p className="field-error">{errors['network.address']}</p>}

        <label htmlFor="network-gateway">Gateway</label>
        <input
          id="network-gateway"
          value={doc.network.gateway}
          onChange={(e) => setDoc({ ...doc, network: { ...doc.network, gateway: e.target.value } })}
        />

        <label htmlFor="storage-pool">Storage pool</label>
        <input
          id="storage-pool"
          value={doc.storage.pool}
          onChange={(e) => setDoc({ ...doc, storage: { ...doc.storage, pool: e.target.value } })}
        />

        <label htmlFor="domains">Intended domains</label>
        <input
          id="domains"
          value={doc.domains.intended.join(', ')}
          onChange={(e) =>
            setDoc({
              ...doc,
              domains: {
                intended: e.target.value
                  .split(',')
                  .map((part) => part.trim())
                  .filter(Boolean),
              },
            })
          }
        />

        {INTENT_KEYS.map((key) => (
          <fieldset key={key}>
            <legend>{key}</legend>
            <label htmlFor={`intent-${key}-mode`}>Mode</label>
            <select
              id={`intent-${key}-mode`}
              value={doc.intent[key]?.mode ?? (key === 'dns' ? 'greenfield' : 'build')}
              onChange={(e) =>
                setDoc({
                  ...doc,
                  intent: { ...doc.intent, [key]: { ...doc.intent[key], mode: e.target.value } },
                })
              }
            >
              {key === 'dns' ? (
                <>
                  <option value="greenfield">greenfield</option>
                  <option value="brownfield">brownfield</option>
                </>
              ) : (
                <>
                  <option value="build">build</option>
                  <option value="adopt">adopt</option>
                </>
              )}
            </select>
            {(doc.intent[key]?.mode === 'adopt' || doc.intent[key]?.mode === 'brownfield') && (
              <>
                <label htmlFor={`intent-${key}-url`}>URL</label>
                <input
                  id={`intent-${key}-url`}
                  value={doc.intent[key]?.url ?? ''}
                  onChange={(e) =>
                    setDoc({
                      ...doc,
                      intent: { ...doc.intent, [key]: { ...doc.intent[key], url: e.target.value } },
                    })
                  }
                />
              </>
            )}
          </fieldset>
        ))}

        <button type="submit">Save schema</button>
        <button type="button" onClick={handleValidate}>
          Validate
        </button>
        <button type="button" onClick={handleExport}>
          Export YAML
        </button>
      </form>

      <h3>Probes</h3>
      <ul aria-label="probes">
        {READONLY_PROBES.map((id) => {
          const result = doc.probes[id]
          return (
            <li key={id}>
              <span>
                {id}: {result?.status ?? 'not run'}
              </span>
              <button type="button" onClick={() => handleProbe(id)}>
                Re-run {id}
              </button>
            </li>
          )
        })}
        <li>ssh_key_installed: {doc.probes.ssh_key_installed?.status ?? 'not run'} (via chat approval)</li>
      </ul>
      {status && <p role="status">{status}</p>}
    </section>
  )
}
