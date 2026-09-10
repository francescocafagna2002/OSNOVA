import { Activity, BatteryCharging, Car, Sun, Waves } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const assets = [
  { icon: Car, label: "Electric vehicles" },
  { icon: Waves, label: "Heat pumps" },
  { icon: Sun, label: "Rooftop PV" },
  { icon: BatteryCharging, label: "Batteries" },
] as const;

const stack = [
  "Next.js 16",
  "React 19",
  "TypeScript",
  "Tailwind v4",
  "shadcn/ui",
  "ECharts",
  "MapLibre",
  "TanStack Query",
  "Zustand",
];

export default function Home() {
  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <Badge variant="secondary" className="mb-2 w-fit gap-1.5">
            <Activity className="size-3.5" />
            Energy Data Hackdays 2026
          </Badge>
          <CardTitle className="text-2xl">OSNOVA — Energy Fingerprints</CardTitle>
          <CardDescription>
            Identify distinctive devices from a household&apos;s aggregated
            15-minute smart-meter signal — with the evidence behind each guess.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {assets.map(({ icon: Icon, label }) => (
              <div
                key={label}
                className="flex flex-col items-center gap-2 rounded-lg border p-4 text-center"
              >
                <Icon className="size-5 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">{label}</span>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-1.5">
            {stack.map((tech) => (
              <Badge key={tech} variant="outline">
                {tech}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
