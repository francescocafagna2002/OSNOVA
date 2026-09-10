"use client";

import { ElectricityChart } from "@/components/chart/electricity-chart";
import { PredictionCards } from "@/components/detail/prediction-cards";
import { PredictionExplanation } from "@/components/detail/prediction-explanation";
import { TechnicalDetails } from "@/components/detail/technical-details";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useSelectedBuilding } from "@/hooks/use-buildings";
import { useUIStore } from "@/stores/ui-store";

/** Desktop width per spec D6; the inline style beats the generated `sm:max-w-sm`. */
const SHEET_STYLE = { width: "min(100vw, 640px)", maxWidth: "none" } as const;

export function BuildingDetailSheet() {
  const building = useSelectedBuilding();
  const isDetailOpen = useUIStore((s) => s.isDetailOpen);
  const closeDetail = useUIStore((s) => s.closeDetail);
  const open = isDetailOpen && building !== undefined;

  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (!next) closeDetail();
      }}
    >
      <SheetContent side="right" className="overflow-y-auto" style={SHEET_STYLE}>
        {building && (
          <>
            <SheetHeader>
              <SheetTitle>Building {building.id}</SheetTitle>
              <SheetDescription>
                {building.postcode} {building.city}, {building.canton}
              </SheetDescription>
            </SheetHeader>
            <div className="space-y-6 px-4 pb-6">
              <PredictionCards predictions={building.predictions} explanation={building.explanation} />
              <section>
                <h3 className="mb-2 text-sm font-semibold">Electricity profile — Last 24 hours</h3>
                <ElectricityChart electricity={building.electricity} events={building.events} />
              </section>
              <PredictionExplanation />
              <TechnicalDetails explanation={building.explanation} predictions={building.predictions} />
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
