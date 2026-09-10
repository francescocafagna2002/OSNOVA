/** Static for the MVP (task doc §12); the sentence on the model is generic on purpose. */
export function PredictionExplanation() {
  return (
    <section className="rounded-lg bg-[#F6F9FB] p-5">
      <h3 className="mb-1 font-serif text-lg font-semibold text-navy">How is this calculated?</h3>
      <p className="text-[14.5px] leading-[1.55] text-foreground">
        The prediction is based on electricity meter measurements recorded every 15 minutes. The model looks for
        recurring patterns in the building&apos;s electricity consumption and compares them with patterns
        associated with known energy assets such as PV systems, EVs, heat pumps and batteries. Every result is a
        probability, not a confirmed installation.
      </p>
    </section>
  );
}
