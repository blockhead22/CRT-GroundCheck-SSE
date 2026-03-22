import { useEffect, useMemo, useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getDoc, listDocs } from '../lib/api'

type DocTab = 'architecture' | 'faq' | 'functional_spec' | 'reference'

const SECTIONS: Array<{ heading: string; items: Array<{ id: DocTab; label: string }> }> = [
  {
    heading: 'Getting Started',
    items: [
      { id: 'architecture', label: 'Architecture' },
      { id: 'faq', label: 'FAQ' },
    ],
  },
  {
    heading: 'Specification',
    items: [
      { id: 'functional_spec', label: 'Functional Spec' },
    ],
  },
  {
    heading: 'API Reference',
    items: [
      { id: 'reference', label: 'Endpoints' },
    ],
  },
]

// ── Heading extraction for TOC ──
function extractHeadings(md: string): Array<{ level: number; text: string; id: string }> {
  const headings: Array<{ level: number; text: string; id: string }> = []
  for (const line of md.split('\n')) {
    const match = line.match(/^(#{1,3})\s+(.+)$/)
    if (match) {
      const text = match[2].replace(/[`*_~]/g, '')
      const id = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
      headings.push({ level: match[1].length, text, id })
    }
  }
  return headings
}

// ── Extract code blocks from markdown for the right panel ──
function extractCodeBlocks(md: string): Array<{ language: string; code: string; label: string }> {
  const blocks: Array<{ language: string; code: string; label: string }> = []
  const regex = /```(\w+)?\n([\s\S]*?)```/g
  let m
  while ((m = regex.exec(md)) !== null) {
    const lang = m[1] || 'text'
    blocks.push({ language: lang, code: m[2].trimEnd(), label: lang.toUpperCase() })
  }
  return blocks
}

// ── Code block with copy + line numbers ──
function CodePanel({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false)
  const lines = code.split('\n')

  function handleCopy() {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: '1px solid rgba(240,235,225,0.06)' }}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2"
        style={{ background: 'rgba(0,0,0,0.5)', borderBottom: '1px solid rgba(240,235,225,0.04)' }}
      >
        <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: '#e8843a' }}>
          {language || 'code'}
        </span>
        <button
          onClick={handleCopy}
          className="text-[10px] font-mono px-2 py-0.5 rounded transition-all hover:bg-white/[0.06]"
          style={{ color: copied ? '#6abf7b' : '#5a5445' }}
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      {/* Code with line numbers */}
      <div className="overflow-x-auto" style={{ background: 'rgba(0,0,0,0.35)' }}>
        <table className="w-full">
          <tbody>
            {lines.map((line, i) => (
              <tr key={i} className="hover:bg-white/[0.02]">
                <td
                  className="select-none text-right px-3 py-0 text-[12px] font-mono align-top"
                  style={{ color: '#332e22', width: '1%', whiteSpace: 'nowrap', userSelect: 'none' }}
                >
                  {i + 1}
                </td>
                <td className="px-3 py-0 text-[13px] font-mono whitespace-pre" style={{ color: '#F0EBE1' }}>
                  {line || ' '}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Inline code block (in prose) ──
function InlineCodeBlock({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="group relative my-4 rounded-xl overflow-hidden" style={{ border: '1px solid rgba(240,235,225,0.06)' }}>
      <div className="flex items-center justify-between px-4 py-2" style={{ background: 'rgba(0,0,0,0.4)', borderBottom: '1px solid rgba(240,235,225,0.04)' }}>
        <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: '#5a5445' }}>{language || 'code'}</span>
        <button onClick={handleCopy} className="text-[10px] font-mono px-2 py-0.5 rounded transition-all hover:bg-white/[0.06]" style={{ color: copied ? '#6abf7b' : '#5a5445' }}>
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 text-[13px] leading-relaxed font-mono" style={{ background: 'rgba(0,0,0,0.3)', color: '#F0EBE1' }}>
        <code>{code}</code>
      </pre>
    </div>
  )
}

// ── Markdown components ──
const docsMdComponents = {
  p({ children }: { children?: React.ReactNode }) {
    return <p className="mb-4 last:mb-0 text-[15px] leading-[1.85]" style={{ color: 'rgba(240,235,225,0.7)' }}>{children}</p>
  },
  ul({ children }: { children?: React.ReactNode }) {
    return <ul className="mb-4 space-y-1.5 pl-5 list-disc" style={{ color: 'rgba(240,235,225,0.55)' }}>{children}</ul>
  },
  ol({ children }: { children?: React.ReactNode }) {
    return <ol className="mb-4 list-decimal space-y-1.5 pl-5" style={{ color: 'rgba(240,235,225,0.55)' }}>{children}</ol>
  },
  li({ children }: { children?: React.ReactNode }) {
    return <li className="text-[15px] leading-relaxed" style={{ color: 'rgba(240,235,225,0.65)' }}>{children}</li>
  },
  code({ children, className }: { children?: React.ReactNode; className?: string }) {
    const codeText = String(children ?? '').replace(/\n$/, '')
    const match = /language-([a-zA-Z0-9_-]+)/.exec(className || '')
    const language = match ? match[1] : undefined
    const isBlock = Boolean(language) || codeText.includes('\n')
    if (!isBlock) {
      return (
        <code className="rounded px-1.5 py-0.5 font-mono text-[0.88em]" style={{ background: 'rgba(201,95,40,0.1)', color: '#e8a86a' }}>
          {children}
        </code>
      )
    }
    return <InlineCodeBlock code={codeText} language={language} />
  },
  blockquote({ children }: { children?: React.ReactNode }) {
    return (
      <blockquote className="my-4 pl-4 py-2 pr-4" style={{ borderLeft: '3px solid rgba(201,95,40,0.35)', color: 'rgba(240,235,225,0.55)' }}>
        {children}
      </blockquote>
    )
  },
  h1({ children }: { children?: React.ReactNode }) {
    const text = String(children ?? '')
    const id = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
    return <h1 id={id} className="mb-4 mt-12 first:mt-0 text-[28px] font-bold text-white scroll-mt-6">{children}</h1>
  },
  h2({ children }: { children?: React.ReactNode }) {
    const text = String(children ?? '')
    const id = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
    return (
      <h2 id={id} className="mb-3 mt-10 text-[22px] font-semibold text-white/95 scroll-mt-6 pb-2" style={{ borderBottom: '1px solid rgba(240,235,225,0.06)' }}>
        {children}
      </h2>
    )
  },
  h3({ children }: { children?: React.ReactNode }) {
    const text = String(children ?? '')
    const id = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
    return <h3 id={id} className="mb-2 mt-6 text-[18px] font-semibold text-white/90 scroll-mt-6">{children}</h3>
  },
  a({ children, href }: { children?: React.ReactNode; href?: string }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 transition-colors hover:text-[#e8843a]" style={{ color: '#e8a86a', textDecorationColor: 'rgba(232,132,58,0.3)' }}>
        {children}
      </a>
    )
  },
  hr() {
    return <hr className="my-8" style={{ borderColor: 'rgba(240,235,225,0.06)' }} />
  },
  table({ children }: { children?: React.ReactNode }) {
    return (
      <div className="my-5 overflow-x-auto rounded-lg" style={{ border: '1px solid rgba(240,235,225,0.06)' }}>
        <table className="w-full text-sm">{children}</table>
      </div>
    )
  },
  th({ children }: { children?: React.ReactNode }) {
    return (
      <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider" style={{ background: 'rgba(0,0,0,0.25)', color: '#a09880', borderBottom: '1px solid rgba(240,235,225,0.06)' }}>
        {children}
      </th>
    )
  },
  td({ children }: { children?: React.ReactNode }) {
    return <td className="px-4 py-2.5 text-[14px]" style={{ color: 'rgba(240,235,225,0.65)', borderBottom: '1px solid rgba(240,235,225,0.03)' }}>{children}</td>
  },
}

// ── Main Component ──
export function DocsPage({ onBackToApp }: { onBackToApp?: () => void }) {
  const [docs, setDocs] = useState<Array<{ id: string; title: string; kind: string }>>([])
  const [activeDocId, setActiveDocId] = useState<string>('architecture')
  const [tab, setTab] = useState<DocTab>('architecture')
  const [md, setMd] = useState<string>('')
  const [title, setTitle] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const [codeTab, setCodeTab] = useState(0)

  useEffect(() => {
    let mounted = true
    listDocs()
      .then((items) => { if (mounted) setDocs(items) })
      .catch((e) => { if (mounted) setError(e instanceof Error ? e.message : String(e)) })
    return () => { mounted = false }
  }, [])

  const filtered = useMemo(() => {
    if (tab === 'reference') return docs.filter((d) => d.kind === 'reference')
    return docs.filter((d) => d.id === tab)
  }, [docs, tab])

  useEffect(() => {
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
        setCodeTab(0)
        contentRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
      })
      .catch((e) => { if (mounted) setError(e instanceof Error ? e.message : String(e)) })
    return () => { mounted = false }
  }, [activeDocId])

  const headings = useMemo(() => extractHeadings(md), [md])
  const codeBlocks = useMemo(() => extractCodeBlocks(md), [md])

  function scrollToHeading(id: string) {
    const el = document.getElementById(id)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="flex h-full min-h-0 flex-col">

      {/* ── Top Bar ── */}
      <div
        className="flex-shrink-0 flex items-center justify-between px-5 py-2.5"
        style={{
          borderBottom: '1px solid rgba(240,235,225,0.06)',
          background: 'rgba(14,13,11,0.8)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
        }}
      >
        <div className="flex items-center gap-3">
          {onBackToApp && (
            <button
              onClick={onBackToApp}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[13px] transition-all hover:bg-white/[0.06]"
              style={{ color: '#a09880' }}
            >
              <span>←</span>
              <span className="hidden sm:inline">App</span>
            </button>
          )}
          {onBackToApp && <div className="h-4 w-px bg-white/[0.08]" />}
          <div className="flex items-center gap-2">
            <div
              className="grid h-7 w-7 place-items-center rounded-lg text-xs font-bold text-white"
              style={{ background: 'var(--accent)' }}
            >
              ⬡
            </div>
            <span className="text-sm font-semibold text-white/90 font-display tracking-wider">DEVELOPERS</span>
          </div>
        </div>
        <div className="flex items-center gap-4 text-[13px]">
          <a href="#" className="text-white/40 hover:text-white/70 transition-colors hidden sm:block">Changelog</a>
          <a href="#" className="text-white/40 hover:text-white/70 transition-colors hidden sm:block">Roadmap</a>
          <a href="#" className="text-white/40 hover:text-white/70 transition-colors hidden md:block">API Status</a>
        </div>
      </div>

      {/* ── Three-column layout ── */}
      <div className="flex flex-1 min-h-0">

        {/* ── LEFT SIDEBAR ── */}
        <nav
          className="hidden lg:flex w-[220px] flex-none flex-col h-full overflow-y-auto py-5 px-4"
          style={{ borderRight: '1px solid rgba(240,235,225,0.05)' }}
        >
          {/* Grouped sections */}
          {SECTIONS.map((section) => (
            <div key={section.heading} className="mb-5">
              <div className="text-[11px] font-semibold uppercase tracking-wider mb-2 px-2" style={{ color: '#e8843a' }}>
                {section.heading}
              </div>
              <div className="flex flex-col gap-px">
                {section.items.map((item) => {
                  const isActive = item.id === tab && item.id !== 'reference'
                  // For reference, render sub-items
                  if (item.id === 'reference') {
                    const refDocs = docs.filter((d) => d.kind === 'reference')
                    const isSectionActive = tab === 'reference'
                    return (
                      <div key={item.id}>
                        <button
                          onClick={() => setTab('reference')}
                          className={
                            'w-full flex items-center justify-between rounded-lg px-2 py-1.5 text-[13px] text-left transition-all ' +
                            (isSectionActive ? 'text-white/90' : 'text-white/45 hover:text-white/70 hover:bg-white/[0.03]')
                          }
                        >
                          <span>{item.label}</span>
                          <span className="text-[10px]" style={{ color: '#5a5445' }}>{isSectionActive ? '▾' : '›'}</span>
                        </button>
                        <AnimatePresence>
                          {isSectionActive && refDocs.length > 0 && (
                            <motion.div
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: 'auto' }}
                              exit={{ opacity: 0, height: 0 }}
                              transition={{ duration: 0.2 }}
                              className="overflow-hidden ml-2"
                              style={{ borderLeft: '1px solid rgba(240,235,225,0.06)' }}
                            >
                              {refDocs.map((d) => (
                                <button
                                  key={d.id}
                                  onClick={() => setActiveDocId(d.id)}
                                  className={
                                    'w-full rounded-r-lg pl-3 pr-2 py-1.5 text-[13px] text-left transition-all ' +
                                    (d.id === activeDocId
                                      ? 'text-white/90 bg-white/[0.06]'
                                      : 'text-white/35 hover:text-white/60 hover:bg-white/[0.03]')
                                  }
                                  style={d.id === activeDocId ? { borderLeft: '2px solid #c95f28', marginLeft: '-1px' } : {}}
                                >
                                  {d.title}
                                </button>
                              ))}
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    )
                  }
                  return (
                    <button
                      key={item.id}
                      onClick={() => setTab(item.id)}
                      className={
                        'w-full rounded-lg px-2 py-1.5 text-[13px] text-left transition-all ' +
                        (isActive
                          ? 'text-white/90 bg-white/[0.06]'
                          : 'text-white/45 hover:text-white/70 hover:bg-white/[0.03]')
                      }
                    >
                      {item.label}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}

          {/* On this page (TOC) */}
          {headings.length > 0 && (
            <div className="mt-2 pt-4" style={{ borderTop: '1px solid rgba(240,235,225,0.05)' }}>
              <div className="text-[10px] font-semibold uppercase tracking-wider mb-2 px-2" style={{ color: '#5a5445' }}>
                On this page
              </div>
              <div className="flex flex-col gap-px">
                {headings.slice(0, 20).map((h, i) => (
                  <button
                    key={`${h.id}-${i}`}
                    onClick={() => scrollToHeading(h.id)}
                    className="text-left text-[12px] rounded-lg px-2 py-1 transition-colors hover:bg-white/[0.04] truncate"
                    style={{
                      paddingLeft: `${(h.level - 1) * 10 + 8}px`,
                      color: h.level === 1 ? 'rgba(240,235,225,0.5)' : 'rgba(240,235,225,0.3)',
                    }}
                  >
                    {h.text}
                  </button>
                ))}
              </div>
            </div>
          )}
        </nav>

        {/* ── CENTER CONTENT ── */}
        <div className="flex-1 min-w-0 flex flex-col h-full">
          {/* Mobile tab bar */}
          <div className="lg:hidden flex-shrink-0 px-4 pt-3 pb-2 overflow-x-auto">
            <div className="flex gap-1">
              {SECTIONS.flatMap((s) => s.items).map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={
                    'flex-none rounded-full px-3 py-1.5 text-xs font-medium transition-all ' +
                    (t.id === tab ? 'text-white' : 'bg-white/[0.04] text-white/50')
                  }
                  style={t.id === tab ? { background: 'var(--accent)' } : {}}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          <div ref={contentRef} className="flex-1 min-h-0 overflow-y-auto">
            <div className="mx-auto w-full max-w-[720px] px-6 md:px-10 py-8 md:py-10">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeDocId}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                >
                  {/* Title */}
                  <h1 className="text-[32px] font-bold text-white mb-3 leading-tight">{title || '—'}</h1>
                  <div className="h-px mb-8" style={{ background: 'linear-gradient(90deg, rgba(201,95,40,0.4) 0%, transparent 50%)' }} />

                  {error && (
                    <div className="rounded-xl p-4 mb-6 text-sm" style={{ border: '1px solid rgba(224,92,32,0.2)', background: 'rgba(224,92,32,0.06)', color: '#fb7185' }}>
                      {error}
                    </div>
                  )}

                  <div className="docs-prose">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={docsMdComponents as any}>
                      {md}
                    </ReactMarkdown>
                  </div>

                  <div className="h-20" />
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </div>

        {/* ── RIGHT CODE PANEL ── */}
        <div
          className="hidden xl:flex w-[340px] flex-none flex-col h-full overflow-hidden"
          style={{
            borderLeft: '1px solid rgba(240,235,225,0.05)',
            background: 'rgba(0,0,0,0.25)',
          }}
        >
          {/* Tab bar */}
          {codeBlocks.length > 0 && (
            <div
              className="flex-shrink-0 flex items-center gap-px px-4 py-3"
              style={{ borderBottom: '1px solid rgba(240,235,225,0.05)' }}
            >
              {codeBlocks.slice(0, 5).map((block, i) => (
                <button
                  key={i}
                  onClick={() => setCodeTab(i)}
                  className={
                    'rounded-lg px-3 py-1 text-[11px] font-mono transition-all ' +
                    (codeTab === i
                      ? 'text-white/90 bg-white/[0.08]'
                      : 'text-white/30 hover:text-white/60 hover:bg-white/[0.04]')
                  }
                >
                  {block.label}
                </button>
              ))}
            </div>
          )}

          {/* Code content */}
          <div className="flex-1 overflow-y-auto p-4">
            {codeBlocks.length > 0 ? (
              <AnimatePresence mode="wait">
                <motion.div
                  key={`${activeDocId}-${codeTab}`}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15 }}
                >
                  <CodePanel
                    code={codeBlocks[codeTab]?.code ?? ''}
                    language={codeBlocks[codeTab]?.language}
                  />
                </motion.div>
              </AnimatePresence>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center px-6">
                <div className="text-[40px] mb-3 opacity-10">⬡</div>
                <div className="text-[13px] text-white/20">No code examples</div>
                <div className="text-[11px] text-white/10 mt-1">Code blocks from the doc will appear here</div>
              </div>
            )}

            {/* Additional code blocks below */}
            {codeBlocks.length > 1 && (
              <div className="mt-6 space-y-4">
                <div className="text-[10px] font-mono uppercase tracking-wider" style={{ color: '#5a5445' }}>
                  All examples
                </div>
                {codeBlocks.map((block, i) => (
                  <div key={i}>
                    <div className="text-[10px] font-mono mb-1.5" style={{ color: '#5a5445' }}>
                      Example {i + 1} — {block.label}
                    </div>
                    <CodePanel code={block.code} language={block.language} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
