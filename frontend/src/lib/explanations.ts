import { getPredictionLabel, type PredictionLabel } from "@/lib/predictions";
import type { AssetKey } from "@/lib/types";

/**
 * Plain-language wording for the technical prediction details.
 *
 * The model's SHAP features carry data-science names ("Midday net-load dip"). This module maps
 * each one to a sentence a customer adviser can read aloud, and gives every asset a one-line
 * summary per label. Unknown feature names fall back to the raw name so a new backend feature
 * still renders.
 */

/** Feature name from the model → what it means in everyday words. */
const SIGNAL_DESCRIPTIONS: Record<string, string> = {
  // PV
  "Midday net-load dip": "Uses less electricity from the grid around midday",
  "Clear-sky day correlation": "Uses even less on sunny days",
  "Seasonal amplitude": "The midday effect is stronger in summer than in winter",
  "Nighttime baseline": "Night-time usage looks like a normal household",
  // Battery
  "Evening peak flattening": "The evening usage peak is smoother than usual",
  "Midday absorption": "Extra midday solar power is kept in the building instead of sent to the grid",
  "Cycle regularity": "Charging and discharging follow a regular daily rhythm",
  "Export events": "How often power is sent back to the grid",
  // Heat pump
  "Cycling frequency": "A 1–2 kW load switches on and off at regular intervals",
  "Temperature sensitivity": "Usage goes up when it gets colder outside",
  "Morning baseline": "Steady higher usage in the early morning",
  "Summer consumption": "How much electricity is used in summer",
  // EV
  "High nighttime power peak": "Very high power draw during the night",
  "Repeated 7 kW events": "Repeated bursts of around 7 kW, typical for car charging",
  "Event duration": "Each burst lasts a few hours",
  "Daytime consumption pattern": "Daytime usage looks like a normal household",
};

/** A short, everyday-words description of a model feature. Falls back to the feature name itself. */
export function describeSignal(feature: string): string {
  return SIGNAL_DESCRIPTIONS[feature] ?? feature;
}

const SUMMARIES: Record<AssetKey, Record<PredictionLabel, string>> = {
  pv: {
    Likely:
      "The building draws noticeably less electricity from the grid around midday. That is exactly what we expect when solar panels on the roof are producing power.",
    Possible:
      "There are some signs of lower grid usage around midday, but the pattern is not regular enough to be sure that solar panels are installed.",
    Unlikely:
      "Grid usage around midday looks like a normal household without solar panels, so a PV system is unlikely.",
  },
  heatPump: {
    Likely:
      "A load of about 1–2 kW switches on and off at regular intervals, and usage rises when it gets colder outside. This is the typical signature of a heat pump.",
    Possible:
      "Some regular on/off switching is visible, but it is not clear enough to be confident that a heat pump is installed.",
    Unlikely:
      "No regular on/off switching load was found, and usage does not react to the outdoor temperature, so a heat pump is unlikely.",
  },
  battery: {
    Likely:
      "Evening usage peaks are smoother than in similar households, and midday solar surplus is kept in the building rather than sent to the grid. This points to a home battery.",
    Possible:
      "Some smoothing of the evening peak is visible, but the charge and discharge pattern is not consistent enough to be sure.",
    Unlikely:
      "Evening usage and midday exports look like a household without storage, so a battery is unlikely.",
  },
  ev: {
    Likely:
      "Repeated bursts of several kilowatts appear mostly at night and last a few hours. This is how charging an electric car looks in the meter data.",
    Possible:
      "Some high-power bursts appear in the data, but not regularly enough to be sure that an electric car is charged here.",
    Unlikely:
      "No repeated high-power bursts were found, and night-time usage stays close to the normal level, so an electric car is unlikely.",
  },
};

/** One plain sentence explaining why the model landed on this probability. */
export function summarizePrediction(assetKey: AssetKey, probability: number): string {
  return SUMMARIES[assetKey][getPredictionLabel(probability)];
}
