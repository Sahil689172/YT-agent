export default function NeoTextarea({ id, label, className = '', rows = 6, disabled, ...props }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {label && (
        <label htmlFor={id} className="block text-xs font-medium uppercase tracking-wider text-white/40">
          {label}
        </label>
      )}
      <div className="neo-inset rounded-xl overflow-hidden focus-within:ring-1 focus-within:ring-white/10 transition-shadow">
        <textarea
          id={id}
          rows={rows}
          disabled={disabled}
          className="w-full resize-y bg-transparent px-4 py-3.5 text-[15px] leading-relaxed text-white placeholder:text-white/25 outline-none min-h-[140px] disabled:opacity-50"
          {...props}
        />
      </div>
    </div>
  )
}
