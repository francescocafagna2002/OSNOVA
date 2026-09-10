import { PredictionCard } from "@/components/detail/prediction-card";
import { ASSETS } from "@/lib/predictions";
import type { AssetPrediction, BuildingExplanation } from "@/lib/types";

type PredictionCardsProps = { predictions: AssetPrediction; explanation: BuildingExplanation };

/** Exactly four cards, always PV, Battery, Heat pump, EV. */
export function PredictionCards({ predictions, explanation }: PredictionCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {ASSETS.map((asset) => (
        <PredictionCard
          key={asset.key}
          assetKey={asset.key}
          probability={predictions[asset.key]}
          explanation={explanation.assets[asset.key]}
        />
      ))}
    </div>
  );
}
