const DAYS = [
  ["mon", "Mon"],
  ["tue", "Tue"],
  ["wed", "Wed"],
  ["thu", "Thu"],
  ["fri", "Fri"],
  ["sat", "Sat"],
  ["sun", "Sun"],
] as const;
const PERIODS = [
  ["am", "Morning"],
  ["pm", "Afternoon"],
  ["eve", "Evening"],
] as const;

/** null = not stated (kept distinct from "stated: no slots"). */
export function AvailabilityGrid({ value, onChange }: { value: string[] | null; onChange: (v: string[] | null) => void }) {
  const stated = value !== null;
  const set = new Set(value ?? []);
  const toggle = (slot: string) => {
    const next = new Set(set);
    if (next.has(slot)) next.delete(slot);
    else next.add(slot);
    onChange([...next].sort());
  };
  return (
    <fieldset>
      <legend className="label">Weekly availability</legend>
      <div className="mb-3 flex flex-wrap gap-4 text-sm">
        <label className="flex items-center gap-2">
          <input type="radio" name="avail-stated" checked={stated} onChange={() => onChange(value ?? [])} />
          I'll mark the times I'm usually free
        </label>
        <label className="flex items-center gap-2">
          <input type="radio" name="avail-stated" checked={!stated} onChange={() => onChange(null)} />
          Prefer not to say for now
        </label>
      </div>
      {stated && (
        <div className="overflow-x-auto">
          <table className="border-separate border-spacing-1 text-sm">
            <thead>
              <tr>
                <th className="sr-only">Period</th>
                {DAYS.map(([d, l]) => (
                  <th key={d} scope="col" className="px-1 text-xs font-medium text-ink-soft">
                    {l}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {PERIODS.map(([p, pl]) => (
                <tr key={p}>
                  <th scope="row" className="pr-2 text-left text-xs font-medium text-ink-soft">
                    {pl}
                  </th>
                  {DAYS.map(([d, dl]) => {
                    const slot = `${d}-${p}`;
                    const on = set.has(slot);
                    return (
                      <td key={slot}>
                        <button
                          type="button"
                          aria-pressed={on}
                          aria-label={`${dl} ${pl.toLowerCase()}`}
                          onClick={() => toggle(slot)}
                          className={`h-8 w-10 rounded border text-xs ${on ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-paper-raised hover:bg-paper-sunk"}`}
                        >
                          {on ? "✓" : ""}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="hint">
        {stated
          ? `${set.size} slot${set.size === 1 ? "" : "s"} selected. Teams only ever see how many slots you share with them, never the slots themselves.`
          : "Unstated availability gets a neutral score and is shown as “not stated” — it is never treated as “unavailable”."}
      </p>
    </fieldset>
  );
}
