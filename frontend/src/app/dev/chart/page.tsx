"use client";

import { ElectricityChart } from "@/components/chart/electricity-chart";
import { generateMockBuildings } from "@/lib/mock-data";

const [demo, ...others] = generateMockBuildings();

/** Throwaway preview for the chart task; deleted at integration. */
export default function ChartPreviewPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8 p-6">
      <section>
        <h2 className="mb-2 text-sm font-semibold">Demo building {demo.id}</h2>
        <ElectricityChart electricity={demo.electricity} events={demo.events} />
      </section>
      {others.slice(0, 3).map((building) => (
        <section key={building.id}>
          <h2 className="mb-2 text-sm font-semibold">{building.id}</h2>
          <ElectricityChart electricity={building.electricity} events={building.events} />
        </section>
      ))}
    </div>
  );
}
