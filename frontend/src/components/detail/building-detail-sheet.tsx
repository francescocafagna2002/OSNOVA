"use client";

import { ElectricityChart } from "@/components/chart/electricity-chart";
import { PredictionCards } from "@/components/detail/prediction-cards";
import { TechnicalDetails } from "@/components/detail/technical-details";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useSelectedBuilding } from "@/hooks/use-buildings";
import { useUIStore } from "@/stores/ui-store";

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
      <SheetContent side="right" className="overflow-y-auto">
        {building && (
          <>
            <SheetHeader className="gap-0.5 p-6">
              <SheetTitle className="text-2xl font-semibold text-navy">Building {building.id}</SheetTitle>
              <SheetDescription>
                {building.postcode} {building.city}, {building.canton}
              </SheetDescription>
            </SheetHeader>
            <div className="space-y-8 px-6 pb-6">
              <PredictionCards predictions={building.predictions} explanation={building.explanation} />
              <section>
                <h3 className="mb-3 text-lg font-semibold text-navy">
                  Electricity profile — Last 24 hours
                </h3>
                <ElectricityChart electricity={building.electricity} events={building.events} />
              </section>
              <TechnicalDetails explanation={building.explanation} predictions={building.predictions} />
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
