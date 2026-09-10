/** Static for the MVP (task doc §12); the sentence on the model is generic on purpose. */
export function PredictionExplanation() {
  return (
    <section className="rounded-xl bg-muted/50 p-4 text-sm leading-relaxed">
      <h3 className="mb-1 font-semibold">How is this calculated?</h3>
      <p className="text-foreground/90">
        The prediction is based on electricity meter measurements recorded every 15 minutes. The model looks for
        recurring patterns in the building&apos;s electricity consumption and compares them with patterns
        associated with known energy assets such as PV systems, EVs, heat pumps and batteries. Every result is a
        probability, not a confirmed installation.
      </p>
    </section>
  );
}
