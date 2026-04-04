import { BackgroundLoopInspector } from '../components/chat/BackgroundLoopInspector'

export function LoopsPage(props: { threadId: string }) {
  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-6">
      <div>
        <div className="text-lg font-semibold text-white">Background Loops</div>
        <div className="mt-1 text-sm text-white/60">
          Live stream of reflection and personality loops (limited scope).
        </div>
      </div>

      <div className="max-w-[980px]">
        <BackgroundLoopInspector threadId={props.threadId} />
      </div>
    </div>
  )
}
