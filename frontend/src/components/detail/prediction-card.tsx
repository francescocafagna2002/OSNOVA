"use client";

import { WhyPopover } from "@/components/detail/why-popover";
import { Badge } from "@/components/ui/badge";
import { ASSET_BY_KEY, formatProbability, getPredictionLabel, type PredictionLabel } from "@/lib/predictions";
import type { AssetExplanation, AssetKey } from "@/lib/types";

const LABEL_VARIANT: Record<PredictionLabel, "likely" | "possible" | "unlikely"> = {
  Likely: "likely",
  Possible: "possible",
  Unlikely: "unlikely",
};

type PredictionCardProps = { assetKey: AssetKey; probability: number; explanation: AssetExplanation };

export function PredictionCard({ assetKey, probability, explanation }: PredictionCardProps) {
  const meta = ASSET_BY_KEY[assetKey];
  const Icon = meta.icon;
  const label = getPredictionLabel(probability);
  return (
    <div
      data-testid={`prediction-card-${assetKey}`}
      className="flex flex-col gap-2 rounded-2xl border border-border bg-white p-4"
    >
      <div className="flex items-center gap-1.5 text-[13px] font-medium text-muted-foreground">
        <Icon className="size-5" style={{ color: meta.color }} aria-hidden />
        {meta.label}
      </div>
      <div className="font-serif text-[34px] leading-none font-semibold text-navy tabular-nums">
        {formatProbability(probability)}
      </div>
      <div className="flex items-center justify-between gap-2">
        <Badge variant={LABEL_VARIANT[label]}>{label}</Badge>
        <WhyPopover assetKey={assetKey} probability={probability} explanation={explanation} />
      </div>
    </div>
  );
}
