import { motion } from 'framer-motion'
import type { QuickAction } from '../types'

export function QuickCards(props: { actions: QuickAction[]; onPick: (a: QuickAction) => void }) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
      {props.actions.map((a) => (
        <motion.button
          key={a.id}
          whileHover={{ y: -2 }}
          whileTap={{ scale: 0.99 }}
          onClick={() => props.onPick(a)}
          className="group rounded-2xl border border-white/10 bg-white/5 p-4 text-left shadow-card backdrop-blur-xl hover:bg-white/10"
        >
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-violet-600/20 text-violet-200">
              <span className="text-base">{a.icon}</span>
            </div>
            <div className="text-sm font-semibold text-white">{a.title}</div>
          </div>
          <div className="mt-2 text-xs leading-5 text-white/60">{a.subtitle}</div>
          <div className="mt-3 h-px w-full bg-gradient-to-r from-transparent via-white/10 to-transparent opacity-0 transition group-hover:opacity-100" />
        </motion.button>
      ))}
    </div>
  )
}
