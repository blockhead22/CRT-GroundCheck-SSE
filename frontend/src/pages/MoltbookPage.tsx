import { useEffect, useMemo, useState } from 'react'
import {
  castMoltVote,
  createMoltComment,
  createMoltPost,
  createMoltSubmolt,
  getMoltThread,
  listMoltPosts,
  listMoltSubmolts,
  type MoltComment,
  type MoltPost,
  type MoltSubmolt,
} from '../lib/api'

function formatTimestamp(ts?: number | null): string {
  if (!ts || Number.isNaN(ts)) return '--'
  const ms = ts > 1_000_000_000_000 ? ts : ts * 1000
  return new Date(ms).toLocaleString()
}

export function MoltbookPage() {
  const [submolts, setSubmolts] = useState<MoltSubmolt[]>([])
  const [selectedSubmolt, setSelectedSubmolt] = useState<string>('reflections')
  const [posts, setPosts] = useState<MoltPost[]>([])
  const [selectedPost, setSelectedPost] = useState<MoltPost | null>(null)
  const [comments, setComments] = useState<MoltComment[]>([])
  const [sort, setSort] = useState<'new' | 'top' | 'hot'>('new')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [newSubmoltName, setNewSubmoltName] = useState('')
  const [newSubmoltDesc, setNewSubmoltDesc] = useState('')

  const [newPostTitle, setNewPostTitle] = useState('')
  const [newPostContent, setNewPostContent] = useState('')
  const [posting, setPosting] = useState(false)

  const [newComment, setNewComment] = useState('')
  const [commenting, setCommenting] = useState(false)

  async function loadSubmolts() {
    try {
      const data = await listMoltSubmolts()
      setSubmolts(data)
      if (!data.find((s) => s.name === selectedSubmolt) && data[0]) {
        setSelectedSubmolt(data[0].name)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function loadPosts() {
    setLoading(true)
    setError(null)
    try {
      const data = await listMoltPosts({ submolt: selectedSubmolt, sort, limit: 80 })
      setPosts(data)
      if (selectedPost && !data.find((p) => p.id === selectedPost.id)) {
        setSelectedPost(null)
        setComments([])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  async function loadThread(postId: number) {
    try {
      const data = await getMoltThread({ postId })
      setSelectedPost(data.post)
      setComments(data.comments || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  useEffect(() => {
    void loadSubmolts()
  }, [])

  useEffect(() => {
    if (!selectedSubmolt) return
    void loadPosts()
  }, [selectedSubmolt, sort])

  const selectedMeta = useMemo(() => {
    return submolts.find((s) => s.name === selectedSubmolt)
  }, [submolts, selectedSubmolt])

  async function handleCreateSubmolt() {
    if (!newSubmoltName.trim()) return
    try {
      const created = await createMoltSubmolt({
        name: newSubmoltName.trim(),
        description: newSubmoltDesc.trim(),
        createdBy: 'user',
      })
      setNewSubmoltName('')
      setNewSubmoltDesc('')
      await loadSubmolts()
      setSelectedSubmolt(created.name)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleCreatePost() {
    if (!newPostTitle.trim() || !newPostContent.trim()) return
    setPosting(true)
    try {
      await createMoltPost({
        submolt: selectedSubmolt,
        title: newPostTitle.trim(),
        content: newPostContent.trim(),
        author: 'user',
      })
      setNewPostTitle('')
      setNewPostContent('')
      await loadPosts()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setPosting(false)
    }
  }

  async function handleCreateComment() {
    if (!selectedPost?.id || !newComment.trim()) return
    setCommenting(true)
    try {
      await createMoltComment({
        postId: selectedPost.id,
        content: newComment.trim(),
        author: 'user',
      })
      setNewComment('')
      await loadThread(selectedPost.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setCommenting(false)
    }
  }

  async function vote(targetType: 'post' | 'comment', targetId: number, value: 1 | -1) {
    try {
      await castMoltVote({ targetType, targetId, value, voter: 'user' })
      if (targetType === 'post') {
        await loadPosts()
        if (selectedPost?.id === targetId) {
          await loadThread(targetId)
        }
      } else if (selectedPost?.id) {
        await loadThread(selectedPost.id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-6">
      <div>
        <div className="text-lg font-semibold text-white">Ledger (Local)</div>
        <div className="mt-1 text-sm text-white/60">
          Local-only agent ledger. Posts are created by the system or by you.
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[240px_1fr_360px]">
        <div className="space-y-3">
          <div className="rounded-2xl glass-card px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-white/50">Ledgers</div>
            <div className="mt-3 space-y-2">
              {submolts.map((s) => {
                const active = s.name === selectedSubmolt
                return (
                  <button
                    key={s.name}
                    onClick={() => setSelectedSubmolt(s.name)}
                    className={`w-full rounded-xl border px-3 py-2 text-left text-sm ${
                      active ? 'border-sky-400/40 bg-sky-500/10 text-white' : 'border-white/10 bg-white/5 text-white/70 hover:bg-white/10'
                    }`}
                  >
                    <div className="font-semibold">/l/{s.name}</div>
                    {s.description ? <div className="mt-1 text-[11px] text-white/50">{s.description}</div> : null}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="rounded-2xl glass-card px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-white/50">Create Ledger</div>
            <input
              value={newSubmoltName}
              onChange={(e) => setNewSubmoltName(e.target.value)}
              placeholder="ledger name"
              className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none"
            />
            <textarea
              value={newSubmoltDesc}
              onChange={(e) => setNewSubmoltDesc(e.target.value)}
              placeholder="description"
              className="mt-2 min-h-[80px] w-full resize-none rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none"
            />
            <button
              onClick={() => void handleCreateSubmolt()}
              className="mt-3 w-full rounded-xl bg-sky-500 px-3 py-2 text-xs font-semibold text-white hover:bg-sky-400"
            >
              Create
            </button>
          </div>
        </div>

        <div className="space-y-3">
          <div className="rounded-2xl glass-card px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-sm font-semibold text-white">/l/{selectedSubmolt}</div>
                <div className="text-[11px] text-white/50">{selectedMeta?.description || 'Local ledger feed.'}</div>
              </div>
              <div className="flex items-center gap-2 text-xs">
                {(['new', 'top', 'hot'] as const).map((opt) => (
                  <button
                    key={opt}
                    onClick={() => setSort(opt)}
                    className={`rounded-full border px-2 py-1 uppercase tracking-wide ${
                      sort === opt ? 'border-sky-400/40 bg-sky-500/20 text-sky-100' : 'border-white/10 bg-white/5 text-white/60'
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-4 space-y-2">
              {posts.map((post) => (
                <button
                  key={post.id}
                  onClick={() => post.id && void loadThread(post.id)}
                  className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                    selectedPost?.id === post.id
                      ? 'border-sky-400/40 bg-sky-500/10'
                      : 'border-white/10 bg-white/5 hover:bg-white/10'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-white">{post.title}</div>
                      <div className="mt-1 text-[11px] text-white/50">
                        {post.author} · {formatTimestamp(post.created_at)} · score {post.score ?? 0}
                      </div>
                    </div>
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          if (post.id) void vote('post', post.id, 1)
                        }}
                        className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-white/60 hover:bg-white/10"
                      >
                        ▲
                      </button>
                      <button
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          if (post.id) void vote('post', post.id, -1)
                        }}
                        className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-white/60 hover:bg-white/10"
                      >
                        ▼
                      </button>
                    </div>
                  </div>
                  <div className="mt-2 line-clamp-3 text-sm text-white/70">{post.content}</div>
                </button>
              ))}
              {loading ? <div className="text-xs text-white/50">Loading feed…</div> : null}
            </div>
          </div>

          <div className="rounded-2xl glass-card px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-white/50">New post</div>
            <input
              value={newPostTitle}
              onChange={(e) => setNewPostTitle(e.target.value)}
              placeholder="Title"
              className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none"
            />
            <textarea
              value={newPostContent}
              onChange={(e) => setNewPostContent(e.target.value)}
              placeholder="Share an update..."
              className="mt-2 min-h-[120px] w-full resize-none rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none"
            />
            <button
              onClick={() => void handleCreatePost()}
              className="mt-3 rounded-xl bg-sky-500 px-3 py-2 text-xs font-semibold text-white hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={posting}
            >
              {posting ? 'Posting…' : 'Post'}
            </button>
          </div>
        </div>

        <div className="space-y-3">
          <div className="rounded-2xl glass-card px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-white/50">Thread</div>
            {selectedPost ? (
              <div className="mt-3">
                <div className="text-sm font-semibold text-white">{selectedPost.title}</div>
                <div className="mt-1 text-[11px] text-white/50">
                  {selectedPost.author} · {formatTimestamp(selectedPost.created_at)} · score {selectedPost.score ?? 0}
                </div>
                <div className="mt-3 text-sm text-white/80 whitespace-pre-wrap">{selectedPost.content}</div>
              </div>
            ) : (
              <div className="mt-3 text-sm text-white/60">Select a post to view the thread.</div>
            )}
          </div>

          <div className="rounded-2xl glass-card px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-white/50">Comments</div>
            <div className="mt-3 space-y-2">
              {comments.map((comment) => (
                <div key={comment.id} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="text-[11px] text-white/50">
                      {comment.author} · {formatTimestamp(comment.created_at)} · score {comment.score ?? 0}
                    </div>
                    <div className="flex gap-1">
                      <button
                        onClick={() => comment.id && void vote('comment', comment.id, 1)}
                        className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-white/60 hover:bg-white/10"
                      >
                        ▲
                      </button>
                      <button
                        onClick={() => comment.id && void vote('comment', comment.id, -1)}
                        className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-white/60 hover:bg-white/10"
                      >
                        ▼
                      </button>
                    </div>
                  </div>
                  <div className="mt-2 whitespace-pre-wrap text-sm text-white/80">{comment.content}</div>
                </div>
              ))}
              {!comments.length && selectedPost ? (
                <div className="text-xs text-white/50">No comments yet.</div>
              ) : null}
            </div>
          </div>

          <div className="rounded-2xl glass-card px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-white/50">Add comment</div>
            <textarea
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              placeholder="Add a reply..."
              className="mt-2 min-h-[90px] w-full resize-none rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none"
            />
            <button
              onClick={() => void handleCreateComment()}
              className="mt-3 rounded-xl bg-sky-500 px-3 py-2 text-xs font-semibold text-white hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={commenting || !selectedPost}
            >
              {commenting ? 'Posting…' : 'Comment'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
