import { COMPOUND_COLORS } from '../../constants/f1';

interface Props {
  compound: string;
  className?: string;
}

export default function CompoundBadge({ compound, className = '' }: Props) {
  const color = COMPOUND_COLORS[compound] || '#888';
  const isHard = compound === 'HARD';

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-bold ${className}`}
      style={{
        backgroundColor: `${color}20`,
        color: color,
        border: isHard ? `1px solid ${color}40` : 'none',
      }}
    >
      {compound}
    </span>
  );
}
