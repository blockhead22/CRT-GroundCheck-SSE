import { motion } from 'framer-motion'
import { useState } from 'react'

type CodeLanguage = 'python' | 'javascript' | 'curl'

interface CodeExample {
  language: CodeLanguage
  label: string
  code: string
}

const codeExamples: CodeExample[] = [
  {
    language: 'python',
    label: 'Python',
    code: `from groundcheck import GroundCheck, Memory

# Initialize CRT verifier
verifier = GroundCheck()

# Define memories
memories = [
    Memory(id="m1", text="User works at Microsoft"),
    Memory(id="m2", text="User works at Amazon")
]

# Verify a statement
result = verifier.verify("You work at Amazon", memories)

# Check for contradictions
if result.requires_disclosure:
    print(f"⚠️ Disclosure needed: {result.expected_disclosure}")
else:
    print("✅ No contradictions detected")

# Access contradiction details
if result.contradictions:
    for c in result.contradictions:
        print(f"Conflict: {c.old_value} → {c.new_value}")`,
  },
  {
    language: 'javascript',
    label: 'JavaScript',
    code: `import { GroundCheck, Memory } from 'groundcheck';

// Initialize CRT verifier
const verifier = new GroundCheck();

// Define memories
const memories = [
  new Memory({ id: 'm1', text: 'User works at Microsoft' }),
  new Memory({ id: 'm2', text: 'User works at Amazon' })
];

// Verify a statement
const result = verifier.verify('You work at Amazon', memories);

// Check for contradictions
if (result.requiresDisclosure) {
  console.log('⚠️ Disclosure needed:', result.expectedDisclosure);
} else {
  console.log('✅ No contradictions detected');
}

// Access contradiction details
if (result.contradictions) {
  result.contradictions.forEach(c => {
    console.log(\`Conflict: \${c.oldValue} → \${c.newValue}\`);
  });
}`,
  },
  {
    language: 'curl',
    label: 'cURL',
    code: `# Send a message to CRT API
curl -X POST http://127.0.0.1:8123/chat \\
  -H "Content-Type: application/json" \\
  -d '{
    "threadId": "thread-123",
    "message": "Where do I work?",
    "history": []
  }'

# Response includes:
# - answer: The AI response with disclosure
# - response_type: "speech" or "disclosure"
# - gates_passed: true/false
# - metadata.contradiction_detected: true/false
# - metadata.retrieved_memories: []

# Example response:
{
  "answer": "You work at Amazon (changed from Microsoft).",
  "response_type": "disclosure",
  "gates_passed": true,
  "metadata": {
    "contradiction_detected": true,
    "retrieved_memories": [...]
  }
}`,
  },
]

interface IntegrationCodeWidgetProps {
  defaultLanguage?: CodeLanguage
}

export function IntegrationCodeWidget(props: IntegrationCodeWidgetProps) {
  const [selectedLang, setSelectedLang] = useState<CodeLanguage>(props.defaultLanguage || 'python')
  const [copied, setCopied] = useState(false)

  const currentExample = codeExamples.find((e) => e.language === selectedLang) || codeExamples[0]

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(currentExample.code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/5 shadow-lg backdrop-blur-xl">
      {/* Header */}
      <div className="border-b border-white/10 bg-gradient-to-r from-violet-600/10 to-purple-600/10 p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-600/20 text-lg">💻</div>
            <h3 className="text-lg font-semibold text-white">Integration Code</h3>
          </div>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleCopy}
            className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${
              copied
                ? 'bg-green-600 text-white'
                : 'border border-white/10 bg-white/5 text-white/80 hover:bg-white/10'
            }`}
          >
            {copied ? (
              <>
                <span>✓</span>
                <span>Copied!</span>
              </>
            ) : (
              <>
                <span>📋</span>
                <span>Copy Code</span>
              </>
            )}
          </motion.button>
        </div>

        {/* Language Tabs */}
        <div className="flex gap-2">
          {codeExamples.map((example) => (
            <button
              key={example.language}
              onClick={() => setSelectedLang(example.language)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                selectedLang === example.language
                  ? 'bg-violet-600 text-white shadow-lg'
                  : 'border border-white/10 bg-white/5 text-white/60 hover:bg-white/10 hover:text-white/80'
              }`}
            >
              {example.label}
            </button>
          ))}
        </div>
      </div>

      {/* Code Display */}
      <div className="relative">
        <motion.pre
          key={selectedLang}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="overflow-x-auto bg-black/40 p-6 text-sm leading-relaxed"
        >
          <code className="font-mono text-gray-100">{currentExample.code}</code>
        </motion.pre>

        {/* Language Badge */}
        <div className="absolute right-4 top-4 rounded-full bg-black/60 px-3 py-1 text-xs font-medium text-white/60 backdrop-blur-sm">
          {currentExample.label}
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-white/10 bg-black/20 p-4">
        <div className="flex items-start gap-3">
          <div className="text-xl">💡</div>
          <div className="flex-1">
            <div className="mb-1 text-sm font-medium text-white/90">Quick Start Tip</div>
            <div className="text-xs text-white/60">
              {selectedLang === 'python' && (
                <>
                  Install with <code className="rounded bg-black/40 px-1.5 py-0.5">pip install groundcheck</code> and
                  start tracking contradictions in your Python app.
                </>
              )}
              {selectedLang === 'javascript' && (
                <>
                  Install with <code className="rounded bg-black/40 px-1.5 py-0.5">npm install groundcheck</code> and
                  integrate CRT into your Node.js or browser app.
                </>
              )}
              {selectedLang === 'curl' && (
                <>
                  Make HTTP requests to the CRT API server. Start the server with{' '}
                  <code className="rounded bg-black/40 px-1.5 py-0.5">python crt_api.py</code>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Compact version for embedding in smaller spaces
export function IntegrationCodeWidgetCompact() {
  const [copied, setCopied] = useState(false)

  const quickCode = `# Quick Start
pip install groundcheck
python crt_api.py  # Start server
# Visit http://localhost:5173`

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(quickCode)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  return (
    <div className="overflow-hidden rounded-xl border border-white/10 bg-white/5 shadow-md">
      <div className="flex items-center justify-between border-b border-white/10 bg-black/20 px-4 py-2">
        <div className="text-sm font-medium text-white/80">Quick Start</div>
        <button
          onClick={handleCopy}
          className={`rounded-md px-2 py-1 text-xs font-medium transition ${
            copied ? 'bg-green-600 text-white' : 'bg-white/10 text-white/60 hover:bg-white/20'
          }`}
        >
          {copied ? '✓ Copied' : '📋 Copy'}
        </button>
      </div>
      <pre className="overflow-x-auto bg-black/40 p-3 text-xs">
        <code className="font-mono text-gray-100">{quickCode}</code>
      </pre>
    </div>
  )
}
