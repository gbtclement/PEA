const NEUTRAL = [228, 228, 231];
const UP = [22, 163, 74];
const DOWN = [220, 38, 38];

export function changeColor(pct: number | null | undefined): string {
  const value = Math.max(-3, Math.min(3, pct ?? 0));
  const target = value >= 0 ? UP : DOWN;
  const t = Math.abs(value) / 3;
  const mix = NEUTRAL.map((c, i) => Math.round(c + (target[i] - c) * t));
  return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`;
}

export function scoreColor(score: number | null | undefined): string {
  if (score == null) return "#a1a1aa";
  if (score >= 70) return "#16a34a";
  if (score >= 50) return "#d97706";
  return "#dc2626";
}
