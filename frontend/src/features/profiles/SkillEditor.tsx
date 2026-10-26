import { useId } from "react";
import type { Skill } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { PROFICIENCY_SHORT } from "../projects/labels";

export function SkillEditor({ value, onChange, vocabulary, max = 40 }: { value: Skill[]; onChange: (s: Skill[]) => void; vocabulary: string[]; max?: number }) {
  const listId = useId();
  const update = (i: number, patch: Partial<Skill>) => onChange(value.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  return (
    <div>
      <datalist id={listId}>
        {vocabulary.map((v) => (
          <option key={v} value={v} />
        ))}
      </datalist>
      {value.length > 0 && (
        <div className="hidden grid-cols-[1fr_11rem_9rem_2rem] gap-2 px-1 pb-1 text-xs text-ink-soft sm:grid">
          <span>Skill</span>
          <span>Proficiency</span>
          <span>Type</span>
        </div>
      )}
      <ul className="space-y-2">
        {value.map((s, i) => (
          <li key={i} className="grid grid-cols-1 gap-2 rounded-md border border-line p-2 sm:grid-cols-[1fr_11rem_9rem_2rem] sm:border-0 sm:p-0">
            <input
              className="input"
              aria-label={`Skill ${i + 1}`}
              list={listId}
              value={s.label}
              maxLength={60}
              placeholder="e.g. React, PostgreSQL, Figma, Public speaking"
              onChange={(e) => update(i, { label: e.target.value })}
            />
            <select className="input" aria-label={`Proficiency for skill ${i + 1}`} value={s.proficiency} onChange={(e) => update(i, { proficiency: Number(e.target.value) })}>
              {[1, 2, 3, 4].map((p) => (
                <option key={p} value={p}>
                  {PROFICIENCY_SHORT[p]}
                </option>
              ))}
            </select>
            <select className="input" aria-label={`Type of skill ${i + 1}`} value={s.kind} onChange={(e) => update(i, { kind: e.target.value as Skill["kind"] })}>
              <option value="technical">Technical</option>
              <option value="non_technical">Non-technical</option>
            </select>
            <button type="button" className="rounded p-2 text-ink-faint hover:bg-paper-sunk hover:text-ink" aria-label={`Remove skill ${s.label || i + 1}`} onClick={() => onChange(value.filter((_, j) => j !== i))}>
              ✕
            </button>
          </li>
        ))}
      </ul>
      <Button variant="secondary" size="sm" className="mt-3" disabled={value.length >= max} onClick={() => onChange([...value, { label: "", proficiency: 2, kind: "technical" }])}>
        + Add skill
      </Button>
      <p className="hint">
        1 = learning or tutorial level · 2 = used in one project · 3 = used in several projects or could lead that part · 4 = advanced, able to guide others.
        Spelling variants such as “nodejs” are recognised automatically.
      </p>
    </div>
  );
}
