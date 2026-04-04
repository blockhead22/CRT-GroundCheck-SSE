import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getDoc, listDocs } from '../lib/api'

type DocTab = 'architecture' | 'faq' | 'functional_spec' | 'reference'

function Pill(props: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      onClick={props.onClick}
      className={
        'rounded-xl px-3 py-1.5 text-xs font-semibold ' +
        (props.active ? 'bg-violet-600 text-white' : 'bg-white/5 text-white/80 hover:bg-white/10')
      }
    >
      {props.label}
    </button>
  )
}

export function DocsPage() {
  const [docs, setDocs] = useState<Array<{ id: string; title: string; kind: string }>>([])
  const [activeDocId, setActiveDocId] = useState<string>('architecture')
  const [tab, setTab] = useState<DocTab>('architecture')
  const [md, setMd] = useState<string>('')
  const [title, setTitle] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    listDocs()
      .then((items) => {
        if (!mounted) return
        setDocs(items)
      })
      .catch((e) => {
        if (!mounted) return
        setError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      mounted = false
    }
  }, [])

  const filtered = useMemo(() => {
    if (tab === 'reference') return docs.filter((d) => d.kind === 'reference')
    return docs.filter((d) => d.id === tab)
  }, [docs, tab])

  useEffect(() => {
    // When switching to reference tab, pick first reference doc.
    if (tab === 'reference') {
      const first = docs.find((d) => d.kind === 'reference')
      if (first) setActiveDocId(first.id)
      return
    }
    setActiveDocId(tab)
  }, [tab, docs])

  useEffect(() => {
    let mounted = true
    setError(null)
    getDoc(activeDocId)
      .then((d) => {
        if (!mounted) return
        setTitle(d.title)
        setMd(d.markdown)
      })
      .catch((e) => {
        if (!mounted) return
        setError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      mounted = false
    }
  }, [activeDocId])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-white/10 px-5 py-4">
        <div className="text-lg font-semibold text-white">Docs</div>
        <div className="mt-2 flex flex-wrap gap-2">
          <Pill active={tab === 'architecture'} label="Architecture" onClick={() => setTab('architecture')} />
          <Pill active={tab === 'faq'} label="FAQ" onClick={() => setTab('faq')} />
          <Pill active={tab === 'functional_spec'} label="Functional Spec" onClick={() => setTab('functional_spec')} />
          <Pill active={tab === 'reference'} label="Reference" onClick={() => setTab('reference')} />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        <div className="flex h-full">
          {tab === 'reference' ? (
            <div className="w-[280px] flex-none border-r border-white/10 p-4">
              <div className="text-xs font-semibold tracking-wide text-white/60">Documents</div>
              <div className="mt-3 space-y-1">
                {filtered.map((d) => (
                  <button
                    key={d.id}
                    onClick={() => setActiveDocId(d.id)}
                    className={
                      'w-full rounded-xl px-3 py-2 text-left text-sm ' +
                      (d.id === activeDocId ? 'bg-white/10 text-white' : 'text-white/80 hover:bg-white/10')
                    }
                  >
                    {d.title}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="min-w-0 flex-1 overflow-auto p-5">
            <div className="mb-4 text-xl font-semibold text-white">{title || '—'}</div>
            {error ? (
              <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
                {error}
              </div>
            ) : null}

            <div className="prose prose-invert max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code(props) {
                    const { children, className } = props
                    const isBlock = String(className || '').includes('language-')
                    if (!isBlock) {
                      return (
                        <code className="rounded bg-white/10 px-1 py-0.5 text-[0.9em] text-white/90">{children}</code>
                      )
                    }
                    return (
                      <pre className="overflow-auto rounded-2xl border border-white/10 bg-black/40 p-4">
                        <code className="text-sm text-white/90">{children}</code>
                      </pre>
                    )
                  },
                }}
              >
                {md}
              </ReactMarkdown>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
