"use client";

import { WhyPopover } from "@/components/detail/why-popover";
import { Badge } from "@/components/ui/badge";
import { ASSET_BY_KEY, formatProbability, getPredictionLabel, type PredictionLabel } from "@/lib/predictions";
import type { AssetExplanation, AssetKey } from "@/lib/types";

const LABEL_VARIANT: Record<PredictionLabel, "default" | "secondary" | "outline"> = {
  Likely: "default",
  Possible: "secondary",
  Unlikely: "outline",
};

type PredictionCardProps = { assetKey: AssetKey; probability: number; explanation: AssetExplanation };

export function PredictionCard({ assetKey, probability, explanation }: PredictionCardProps) {
  const meta = ASSET_BY_KEY[assetKey];
  const Icon = meta.icon;
  const label = getPredictionLabel(probability);
  return (
    <div
      data-testid={`prediction-card-${assetKey}`}
      className="flex flex-col gap-2 rounded-xl bg-card p-3 ring-1 ring-foreground/10"
    >
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Icon className="size-4" style={{ color: meta.color }} aria-hidden />
        {meta.label}
      </div>
      <div className="text-2xl font-semibold tabular-nums">{formatProbability(probability)}</div>
      <div className="flex items-center justify-between gap-2">
        <Badge variant={LABEL_VARIANT[label]}>{label}</Badge>
        <WhyPopover assetKey={assetKey} probability={probability} explanation={explanation} />
      </div>
    </div>
  );
}
