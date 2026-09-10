"use client";

import { Info, Search } from "lucide-react";

import { AreaSelect } from "@/components/header/area-select";
import { ViewToggle } from "@/components/header/view-toggle";
import { Wordmark } from "@/components/header/wordmark";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useUIStore } from "@/stores/ui-store";

export function AppHeader() {
  const searchQuery = useUIStore((s) => s.searchQuery);
  const setSearchQuery = useUIStore((s) => s.setSearchQuery);
  const viewMode = useUIStore((s) => s.viewMode);
  const setViewMode = useUIStore((s) => s.setViewMode);
  const setAboutOpen = useUIStore((s) => s.setAboutOpen);

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card px-4">
      <Wordmark />
      <div className="hidden md:block">
        <AreaSelect />
      </div>
      <div className="relative mx-auto w-full max-w-md min-w-0">
        <Search
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          type="search"
          aria-label="Search buildings"
          placeholder="Search building ID, PLZ or town..."
          className="rounded-lg border-border pl-8 focus-visible:ring-2 focus-visible:ring-primary"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
        />
      </div>
      <ViewToggle value={viewMode} onChange={setViewMode} />
      <Button
        variant="ghost"
        size="sm"
        className="hidden sm:inline-flex hover:text-navy"
        onClick={() => setAboutOpen(true)}
      >
        <Info />
        About this project
      </Button>
    </header>
  );
}
