import { ASSET_BY_KEY, describePrediction, formatProbability } from "@/lib/predictions";
import type { AssetKey } from "@/lib/types";

export function ProbabilityChip({ assetKey, probability }: { assetKey: AssetKey; probability: number }) {
  const { icon: Icon, color, shortLabel } = ASSET_BY_KEY[assetKey];
  return (
    <span
      title={describePrediction(assetKey, probability)}
      className="inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-xs font-medium tabular-nums"
      style={{ color }}
    >
      <Icon className="size-3.5" aria-hidden />
      <span className="sr-only">{shortLabel}</span>
      {formatProbability(probability)}
    </span>
  );
}
