"use client";

import { AboutDialog } from "@/components/header/about-dialog";
import { AppHeader } from "@/components/header/app-header";
import { useUIStore } from "@/stores/ui-store";

/** Throwaway preview for the header task; deleted at integration. */
export default function HeaderPreviewPage() {
  const state = useUIStore();
  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader />
      <AboutDialog />
      <pre className="p-4 text-xs text-muted-foreground">
        {JSON.stringify({ viewMode: state.viewMode, searchQuery: state.searchQuery, isAboutOpen: state.isAboutOpen }, null, 2)}
      </pre>
    </div>
  );
}
