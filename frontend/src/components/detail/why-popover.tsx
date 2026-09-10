"use client";

import { Check } from "lucide-react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ASSET_BY_KEY, formatContribution, getPredictionLabel } from "@/lib/predictions";
import type { AssetExplanation, AssetKey, ShapFeature } from "@/lib/types";

const MAX_BARS = 3;

/** Positive contributions only, largest first, at most `max`. */
export function topContributions(shap: ShapFeature[], max = MAX_BARS): ShapFeature[] {
  return shap
    .filter((item) => item.contribution > 0)
    .sort((a, b) => b.contribution - a.contribution)
    .slice(0, max);
}

type WhyPopoverProps = { assetKey: AssetKey; probability: number; explanation: AssetExplanation };

export function WhyPopover({ assetKey, probability, explanation }: WhyPopoverProps) {
  const meta = ASSET_BY_KEY[assetKey];
  const label = getPredictionLabel(probability).toLowerCase();
  const bars = topContributions(explanation.shap);
  const maxContribution = Math.max(0.01, ...bars.map((bar) => bar.contribution));

  return (
    <Popover>
      <PopoverTrigger
        aria-label={`Why ${meta.shortLabel}?`}
        className="text-[13px] font-medium text-primary hover:text-navy hover:underline"
      >
        Why?
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-72 rounded-[12px] border border-border p-3.5 shadow-[0_4px_16px_rgba(20,40,60,0.10)] ring-0"
      >
        <div className="font-serif text-[15px] font-semibold text-navy">
          Why {meta.shortLabel} is {label}
        </div>
        <ul className="mt-2 space-y-1.5 text-sm">
          {explanation.reasons.map((reason) => (
            <li key={reason} className="flex gap-2">
              <Check className="mt-0.5 size-4 shrink-0 text-accent-foreground" aria-hidden />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
        {bars.length > 0 && (
          <div className="mt-3">
            <div className="text-xs font-medium text-muted-foreground">SHAP contribution</div>
            <ul className="mt-1.5 space-y-1.5">
              {bars.map((bar) => (
                <li key={bar.feature} className="text-xs">
                  <div className="flex justify-between gap-2">
                    <span>{bar.feature}</span>
                    <span className="tabular-nums">{formatContribution(bar.contribution)}</span>
                  </div>
                  <div className="mt-0.5 h-1.5 rounded-full bg-[#EEF2F5]">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.round((bar.contribution / maxContribution) * 100)}%`,
                        backgroundColor: meta.color,
                      }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
