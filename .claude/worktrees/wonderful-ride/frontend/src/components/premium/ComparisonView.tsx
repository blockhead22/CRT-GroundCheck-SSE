import { motion } from 'framer-motion'

interface ComparisonViewProps {
  userQuery: string
  regularResponse: string
  crtResponse: string
  contradictions?: Array<{
    slot: string
    oldValue: string
    newValue: string
  }>
}

export function ComparisonView(props: ComparisonViewProps) {
  return (
    <div className="space-y-4">
      <div className="text-center">
        <h3 className="text-lg font-semibold text-white/90">Side-by-Side Comparison</h3>
        <p className="text-sm text-white/60">Regular AI vs CRT Enhanced</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Regular AI Panel */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          className="overflow-hidden rounded-2xl border border-red-500/30 bg-red-500/5"
        >
          <div className="border-b border-red-500/30 bg-red-500/10 px-4 py-3">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-red-300">Regular AI</div>
            <div className="text-xs text-white/50">Without CRT Protection</div>
          </div>

          <div className="p-4">
            <div className="mb-3 rounded-lg bg-black/20 p-3">
              <div className="mb-1 text-xs text-white/40">Query:</div>
              <div className="text-sm text-white/80">{props.userQuery}</div>
            </div>

            <div className="mb-4 rounded-lg bg-black/30 p-3">
              <div className="mb-1 text-xs text-white/40">Response:</div>
              <div className="text-sm text-white">{props.regularResponse}</div>
            </div>

            <div className="space-y-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
              <div className="text-xs font-semibold text-red-300">Issues:</div>
              <div className="space-y-1.5">
                <div className="flex items-start gap-2 text-xs text-red-300">
                  <span className="mt-0.5">⚠️</span>
                  <span>Hides contradictions</span>
                </div>
                <div className="flex items-start gap-2 text-xs text-red-300">
                  <span className="mt-0.5">⚠️</span>
                  <span>No disclosure of changes</span>
                </div>
                <div className="flex items-start gap-2 text-xs text-red-300">
                  <span className="mt-0.5">⚠️</span>
                  <span>Gaslighting risk</span>
                </div>
                <div className="flex items-start gap-2 text-xs text-red-300">
                  <span className="mt-0.5">⚠️</span>
                  <span>No audit trail</span>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* CRT Enhanced Panel */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="overflow-hidden rounded-2xl border border-green-500/30 bg-green-500/5"
        >
          <div className="border-b border-green-500/30 bg-green-500/10 px-4 py-3">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-green-300">CRT Enhanced</div>
            <div className="text-xs text-white/50">With Contradiction Tracking</div>
          </div>

          <div className="p-4">
            <div className="mb-3 rounded-lg bg-black/20 p-3">
              <div className="mb-1 text-xs text-white/40">Query:</div>
              <div className="text-sm text-white/80">{props.userQuery}</div>
            </div>

            <div className="mb-4 rounded-lg border border-green-500/30 bg-black/30 p-3">
              <div className="mb-1 text-xs text-white/40">Response:</div>
              <div className="text-sm text-white">{props.crtResponse}</div>
            </div>

            {props.contradictions && props.contradictions.length > 0 && (
              <div className="mb-4 rounded-lg border border-orange-500/30 bg-orange-500/10 p-3">
                <div className="mb-2 text-xs font-semibold text-orange-300">Contradictions Detected:</div>
                <div className="space-y-2">
                  {props.contradictions.map((c, i) => (
                    <div key={i} className="rounded-md bg-black/30 p-2 text-xs">
                      <div className="mb-1 font-medium text-white/80">Slot: {c.slot}</div>
                      <div className="text-white/60">
                        <div>Old: {c.oldValue}</div>
                        <div>New: {c.newValue}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-2 rounded-lg border border-green-500/30 bg-green-500/10 p-3">
              <div className="text-xs font-semibold text-green-300">Benefits:</div>
              <div className="space-y-1.5">
                <div className="flex items-start gap-2 text-xs text-green-300">
                  <span className="mt-0.5">✅</span>
                  <span>Contradictions disclosed</span>
                </div>
                <div className="flex items-start gap-2 text-xs text-green-300">
                  <span className="mt-0.5">✅</span>
                  <span>Full transparency</span>
                </div>
                <div className="flex items-start gap-2 text-xs text-green-300">
                  <span className="mt-0.5">✅</span>
                  <span>Prevents gaslighting</span>
                </div>
                <div className="flex items-start gap-2 text-xs text-green-300">
                  <span className="mt-0.5">✅</span>
                  <span>Complete audit trail</span>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="rounded-xl bg-gradient-to-r from-violet-500/10 to-purple-500/10 p-4 text-center"
      >
        <div className="mb-1 text-sm font-semibold text-violet-300">The CRT Difference</div>
        <div className="text-xs text-white/60">
          CRT preserves contradictions and enforces disclosure, preventing AI from rewriting history.
        </div>
      </motion.div>
    </div>
  )
}

// Example usage component with sample data
export function ComparisonViewExample() {
  return (
    <ComparisonView
      userQuery="Where do I work?"
      regularResponse="You work at Amazon."
      crtResponse="You work at Amazon (changed from Microsoft in March 2024)."
      contradictions={[
        {
          slot: 'employer',
          oldValue: 'Microsoft',
          newValue: 'Amazon',
        },
      ]}
    />
  )
}
