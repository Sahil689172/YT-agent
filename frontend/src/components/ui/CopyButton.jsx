import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import NeoButton from './NeoButton'

export default function CopyButton({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <NeoButton
      variant="ghost"
      icon={copied ? Check : Copy}
      onClick={handleCopy}
      className="!py-2 !px-3 text-xs"
    >
      {copied ? 'Copied' : label}
    </NeoButton>
  )
}
