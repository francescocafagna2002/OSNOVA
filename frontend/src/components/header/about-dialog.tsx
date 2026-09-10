"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useUIStore } from "@/stores/ui-store";

/** Copy adapted from the repository README ("Challenge" section). */
const ABOUT_PARAGRAPHS = [
  "One smart meter records a household's aggregated electricity signal, but many devices contribute to it. The Energy Fingerprints challenge at Energy Data Hackdays 2026 asks which assets — electric vehicles, heat pumps, rooftop PV and batteries — can be recognised from anonymised 15-minute measurements.",
  "This demo shows, per postal-code area and per anonymised building, how likely each asset is, when it appears to be active, and the evidence behind that estimate. Predictions are probabilities, not facts.",
  "Data: four years of 15-minute smart-meter readings for about 90,000 anonymised customers with postal codes, plus known asset labels for around 1,000 of them. The demo runs on generated mock data shaped like the real contract.",
];

export function AboutDialog() {
  const isAboutOpen = useUIStore((s) => s.isAboutOpen);
  const setAboutOpen = useUIStore((s) => s.setAboutOpen);
  return (
    <Dialog open={isAboutOpen} onOpenChange={(open) => setAboutOpen(open)}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>About this project</DialogTitle>
          <DialogDescription>AEW Energy Fingerprints — Energy Data Hackdays 2026</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 text-sm leading-relaxed text-foreground/90">
          {ABOUT_PARAGRAPHS.map((paragraph) => (
            <p key={paragraph.slice(0, 24)}>{paragraph}</p>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
