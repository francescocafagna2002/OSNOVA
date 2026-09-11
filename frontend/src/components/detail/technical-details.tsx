"use client";

import { ChevronDown, Minus, Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { describeSignal, summarizePrediction } from "@/lib/explanations";
import { ASSET_BY_KEY, formatProbability, getPredictionLabel } from "@/lib/predictions";
import type { AssetKey, AssetPrediction, BuildingExplanation } from "@/lib/types";

/** The order the details are read in: PV, heat pump, battery, EV. */
const DETAIL_ORDER: readonly AssetKey[] = ["pv", "heatPump", "battery", "ev"];

const LABEL_VARIANT = { Likely: "likely", Possible: "possible", Unlikely: "unlikely" } as const;

type TechnicalDetailsProps = { explanation: BuildingExplanation; predictions: AssetPrediction };

export function TechnicalDetails({ explanation, predictions }: TechnicalDetailsProps) {
  return (
    <Collapsible>
      <CollapsibleTrigger className="group flex items-center gap-1 text-sm font-medium text-primary hover:text-navy hover:underline focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:outline-none">
        Show technical prediction details
        <ChevronDown className="size-4 transition-transform group-data-[panel-open]:rotate-180" aria-hidden />
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-3 space-y-4 rounded-lg bg-[#F6F9FB] p-4 text-sm">
        <div className="space-y-3">
          {DETAIL_ORDER.map((key) => {
            const meta = ASSET_BY_KEY[key];
            const Icon = meta.icon;
            const probability = predictions[key];
            const label = getPredictionLabel(probability);
            return (
              <div key={key} data-testid={`technical-${key}`} className="rounded-lg border border-border bg-white p-3.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 text-[14px] font-semibold text-navy">
                    <Icon className="size-4" style={{ color: meta.color }} aria-hidden />
                    <span>
                      {meta.shortLabel} prediction: {formatProbability(probability)}
                    </span>
                  </div>
                  <Badge variant={LABEL_VARIANT[label]}>{label}</Badge>
                </div>
                <p className="mt-1.5 text-[13.5px] leading-[1.55] text-foreground">
                  {summarizePrediction(key, probability)}
                </p>
                <ul className="mt-2.5 space-y-1.5 border-t border-border pt-2.5">
                  {explanation.assets[key].shap.map((item) => {
                    const supports = item.contribution >= 0;
                    return (
                      <li key={item.feature} className="text-[13px]">
                        <span className="flex items-start gap-1.5">
                          {supports ? (
                            <Plus className="mt-0.5 size-3.5 shrink-0 text-accent-foreground" aria-hidden />
                          ) : (
                            <Minus className="mt-0.5 size-3.5 shrink-0 text-destructive" aria-hidden />
                          )}
                          <span>
                            {describeSignal(item.feature)}
                            {describeSignal(item.feature) !== item.feature && (
                              <span className="block text-[11.5px] text-muted-foreground">{item.feature}</span>
                            )}
                          </span>
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </div>

        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 border-t border-border pt-3 text-[13px]">
          <dt className="text-muted-foreground">Model</dt>
          <dd>{explanation.model}</dd>
          <dt className="text-muted-foreground">Based on</dt>
          <dd>{explanation.inputs.join(", ")}</dd>
          <dt className="text-muted-foreground">Extra data</dt>
          <dd>{explanation.additionalData.join(", ") || "None"}</dd>
          <dt className="text-muted-foreground">Method</dt>
          <dd>
            {explanation.method} — {explanation.methodDescription}
          </dd>
        </dl>
      </CollapsibleContent>
    </Collapsible>
  );
}
