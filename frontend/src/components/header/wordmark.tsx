/**
 * Text wordmark. If the team obtains the official AEW logo, drop it in
 * `public/aew-logo.svg` and replace the "AEW" tile with an <Image>.
 */
export function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <div
        aria-hidden
        className="grid size-8 place-items-center rounded-md bg-primary text-[11px] font-bold tracking-wide text-primary-foreground"
      >
        AEW
      </div>
      <div className="leading-tight">
        <div className="text-sm font-semibold">Energy Fingerprints</div>
        <div className="text-[11px] text-muted-foreground">Energy Data Hackdays 2026</div>
      </div>
    </div>
  );
}
