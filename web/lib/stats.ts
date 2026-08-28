export function percentile(sorted: number[], p: number): number | null {
  if (!sorted.length) return null;
  const i = Math.min(sorted.length - 1, Math.floor(sorted.length * p));
  return sorted[i];
}

export function fmtUSD(n: number): string {
  return `$${n.toFixed(n < 0.01 ? 5 : 4)}`;
}
