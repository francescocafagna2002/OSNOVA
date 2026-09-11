/**
 * Text wordmark. If the team obtains the official AEW logo, drop it in
 * `public/aew-logo.svg` and replace the "AEW" tile with an <Image>.
 */
export function Wordmark() {
  return (
    <div className="flex items-center gap-2.5 md:shrink-0">
      <div
        aria-hidden
        className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-[11px] font-bold tracking-wide text-primary-foreground"
      >
        AEW
      </div>
      <div className="leading-tight md:whitespace-nowrap">
        <div className="text-[15px] font-semibold text-navy">Energy Fingerprints</div>
        {/* The subtitle is what pushes the 56 px header onto two lines below ~1280 px. */}
        <div className="hidden text-[11px] text-muted-foreground xl:block">Energy Data Hackdays 2026</div>
      </div>
    </div>
  );
}
