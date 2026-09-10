"use client";

import { ChevronDown } from "lucide-react";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ASSETS, formatContribution, formatProbability } from "@/lib/predictions";
import type { AssetPrediction, BuildingExplanation } from "@/lib/types";
import { cn } from "@/lib/utils";

type TechnicalDetailsProps = { explanation: BuildingExplanation; predictions: AssetPrediction };

export function TechnicalDetails({ explanation, predictions }: TechnicalDetailsProps) {
  return (
    <Collapsible>
      <CollapsibleTrigger className="group flex items-center gap-1 text-sm font-medium text-primary hover:text-navy hover:underline">
        Show technical details
        <ChevronDown className="size-4 transition-transform group-data-[panel-open]:rotate-180" aria-hidden />
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-3 space-y-4 rounded-lg bg-[#F6F9FB] p-4 text-sm">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
          <dt className="text-muted-foreground">Model</dt>
          <dd>{explanation.model}</dd>
          <dt className="text-muted-foreground">Input</dt>
          <dd>{explanation.inputs.join(", ")}</dd>
          <dt className="text-muted-foreground">Additional data</dt>
          <dd>{explanation.additionalData.join(", ") || "None"}</dd>
          <dt className="text-muted-foreground">Explainability</dt>
          <dd>
            {explanation.method} — {explanation.methodDescription}
          </dd>
        </dl>
        <div className="grid gap-3 sm:grid-cols-2">
          {ASSETS.map((asset) => (
            <div key={asset.key} className="rounded-lg border border-border bg-white p-3">
              <div className="mb-1.5 text-xs font-semibold">
                {asset.shortLabel} prediction: {formatProbability(predictions[asset.key])}
              </div>
              <ul className="space-y-0.5 font-mono text-xs">
                {explanation.assets[asset.key].shap.map((item) => (
                  <li key={item.feature} className="flex justify-between gap-2">
                    <span>{item.feature}</span>
                    <span className={cn("tabular-nums", item.contribution < 0 ? "text-destructive" : "text-accent-foreground")}>
                      {formatContribution(item.contribution)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
