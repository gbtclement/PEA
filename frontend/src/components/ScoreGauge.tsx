import { scoreColor } from "@/lib/colors";

export function ScoreGauge({ score, size = 44 }: { score: number | null | undefined; size?: number }) {
  const radius = size / 2 - 4;
  const circumference = 2 * Math.PI * radius;
  const value = score == null ? 0 : Math.max(0, Math.min(100, score));
  const label = score == null ? "Score indisponible" : `Score ${Math.round(value)} sur 100`;
  return (
    <div aria-label={label} role="img" className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e4e4e7" strokeWidth={4} />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={scoreColor(score)} strokeWidth={4}
          strokeDasharray={circumference} strokeDashoffset={circumference * (1 - value / 100)} strokeLinecap="round"
        />
      </svg>
      <span className="absolute text-xs font-semibold">{score == null ? "—" : Math.round(value)}</span>
    </div>
  );
}
