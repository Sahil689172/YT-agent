export default function NeoInput({ id, label, icon: Icon, className = '', disabled, ...props }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {label && (
        <label htmlFor={id} className="block text-xs font-medium uppercase tracking-wider text-white/40">
          {label}
        </label>
      )}
      <div className="relative neo-inset rounded-xl overflow-hidden focus-within:ring-1 focus-within:ring-white/10 transition-shadow">
        {Icon && (
          <div className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none">
            <Icon size={18} strokeWidth={1.75} />
          </div>
        )}
        <input
          id={id}
          disabled={disabled}
          className={`
            w-full bg-transparent py-3.5 text-[15px] text-white placeholder:text-white/25
            outline-none transition-colors focus:text-white disabled:opacity-50
            ${Icon ? 'pl-11 pr-4' : 'px-4'}
          `}
          {...props}
        />
      </div>
    </div>
  )
}
