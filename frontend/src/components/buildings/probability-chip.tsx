import { ASSET_BY_KEY, describePrediction, formatProbability } from "@/lib/predictions";
import type { AssetKey } from "@/lib/types";

export function ProbabilityChip({ assetKey, probability }: { assetKey: AssetKey; probability: number }) {
  const { icon: Icon, color, pillBackground, shortLabel } = ASSET_BY_KEY[assetKey];
  return (
    <span
      title={describePrediction(assetKey, probability)}
      className="inline-flex h-6 items-center gap-1 rounded-full px-2 text-[12.5px] font-medium text-foreground tabular-nums"
      style={{ backgroundColor: pillBackground }}
    >
      <Icon className="size-3.5" style={{ color }} aria-hidden />
      <span className="sr-only">{shortLabel}</span>
      {formatProbability(probability)}
    </span>
  );
}
