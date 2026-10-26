import { useId, useState, type ReactNode, type KeyboardEvent } from "react";

export function Field({ label, hint, error, children, id }: { label: string; hint?: ReactNode; error?: string; children: (id: string) => ReactNode; id?: string }) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <div>
      <label htmlFor={fid} className="label">
        {label}
      </label>
      {children(fid)}
      {hint && !error && <p className="hint">{hint}</p>}
      {error && (
        <p className="mt-1 text-xs text-red-700" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function Toggle({ checked, onChange, label, description }: { checked: boolean; onChange: (v: boolean) => void; label: string; description?: ReactNode }) {
  const id = useId();
  return (
    <div className="flex items-start gap-3">
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative mt-0.5 inline-flex h-5 w-9 shrink-0 rounded-full transition-colors ${checked ? "bg-brand-600" : "bg-line"}`}
      >
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-4" : "translate-x-0.5"}`} />
      </button>
      <div>
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        {description && <p className="text-xs text-ink-soft">{description}</p>}
      </div>
    </div>
  );
}

/** Free-text chips with optional suggestions (datalist). */
export function TagInput({ value, onChange, placeholder, suggestions, max = 15, label }: {
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
  suggestions?: string[];
  max?: number;
  label: string;
}) {
  const [text, setText] = useState("");
  const listId = useId();
  const inputId = useId();
  const add = () => {
    const t = text.trim();
    if (t && !value.some((v) => v.toLowerCase() === t.toLowerCase()) && value.length < max) onChange([...value, t]);
    setText("");
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add();
    } else if (e.key === "Backspace" && !text && value.length) onChange(value.slice(0, -1));
  };
  return (
    <div>
      <label htmlFor={inputId} className="label">
        {label}
      </label>
      <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-line bg-paper-raised p-1.5 focus-within:border-brand-500">
        {value.map((v) => (
          <span key={v} className="inline-flex items-center gap-1 rounded bg-paper-sunk px-2 py-0.5 text-sm">
            {v}
            <button type="button" className="text-ink-faint hover:text-ink" aria-label={`Remove ${v}`} onClick={() => onChange(value.filter((x) => x !== v))}>
              ×
            </button>
          </span>
        ))}
        <input
          id={inputId}
          className="min-w-[8rem] flex-1 bg-transparent px-1 py-0.5 text-sm outline-none"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKey}
          onBlur={add}
          placeholder={value.length ? "" : placeholder}
          list={suggestions ? listId : undefined}
          disabled={value.length >= max}
        />
        {suggestions && (
          <datalist id={listId}>
            {suggestions.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
        )}
      </div>
      <p className="hint">Press Enter to add. {value.length}/{max}</p>
    </div>
  );
}
