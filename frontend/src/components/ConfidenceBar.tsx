type Props = {value: number; label?: string; compact?: boolean};

function tone(value: number) {
  if (value >= 0.75) return 'var(--accent)';
  if (value >= 0.5) return 'var(--warn)';
  return 'var(--danger)';
}

export default function ConfidenceBar({value, label, compact = false}: Props) {
  const percent = Math.round(value * 100);
  return (
    <div className={compact ? 'flex items-center gap-2' : 'space-y-1.5'}>
      {label ? (
        <div className="flex items-baseline justify-between text-xs" style={{color: 'var(--muted)'}}>
          <span>{label}</span>
          <span className="font-mono font-medium" style={{color: tone(value)}}>
            {percent}%
          </span>
        </div>
      ) : null}
      <div
        className={compact ? 'h-1.5 w-14 overflow-hidden rounded-full' : 'h-2 overflow-hidden rounded-full'}
        style={{background: 'var(--border)'}}
        role="meter"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full transition-[width] duration-300"
          style={{width: `${Math.max(2, percent)}%`, background: tone(value)}}
        />
      </div>
      {compact ? (
        <span className="w-9 shrink-0 text-right font-mono text-xs" style={{color: 'var(--muted)'}}>
          {percent}%
        </span>
      ) : null}
    </div>
  );
}
