import { ButtonLink } from "../components/ui/Button";

function ExampleTeam() {
  const rows = [
    { skill: "React (frontend)", have: 1 },
    { skill: "Machine learning", have: 1 },
    { skill: "Node.js (backend)", have: 0 },
    { skill: "PostgreSQL", have: 0 },
  ];
  return (
    <figure className="card p-5" aria-labelledby="example-caption">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Example team · placement-prep web app</p>
      <ul className="mt-3 space-y-2">
        {rows.map((r) => (
          <li key={r.skill} className="flex items-center justify-between gap-4 text-sm">
            <span>{r.skill}</span>
            <span className={r.have ? "text-brand-700" : "font-medium text-gap"}>{r.have ? "covered" : "missing"}</span>
          </li>
        ))}
      </ul>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <div className="rounded-md border border-line p-3 text-sm">
          <p className="font-medium">Candidate X</p>
          <p className="text-ink-soft">Experienced React developer</p>
          <p className="mt-2 text-xs text-ink-faint">Relevant to the project, but repeats a skill the team has.</p>
        </div>
        <div className="rounded-md border-2 border-brand-500 p-3 text-sm">
          <p className="font-medium">Candidate Y</p>
          <p className="text-ink-soft">Node.js + PostgreSQL</p>
          <p className="mt-2 text-xs text-brand-800">Fills both essential gaps → ranked first for this team.</p>
        </div>
      </div>
      <figcaption id="example-caption" className="sr-only">
        A team covering frontend and machine learning needs backend and database skills; Assembl ranks the candidate who fills them first.
      </figcaption>
    </figure>
  );
}

export function LandingPage() {
  return (
    <div>
      <section className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-16 md:grid-cols-[1.1fr_1fr]">
        <div>
          <h1 className="text-4xl font-semibold leading-tight md:text-5xl">Find the teammate your team is actually missing.</h1>
          <p className="mt-5 max-w-xl text-lg text-ink-soft">
            Assembl ranks candidates for a student team by what they would <em>add</em> to the people already on it — the required skills nobody covers yet, the
            open role, and whether you can meet at the same times — and explains every suggestion.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <ButtonLink to="/register">Create an account</ButtonLink>
            <ButtonLink to="/how-it-works" variant="secondary">
              How ranking works
            </ButtonLink>
          </div>
          <p className="mt-6 text-xs text-ink-faint">
            Research prototype. The method follows a proposed framework whose evaluation with real students has not been completed yet.
          </p>
        </div>
        <ExampleTeam />
      </section>
      <section className="border-t border-line bg-paper-raised">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 md:grid-cols-3">
          {[
            ["Relevance is not enough", "Two candidates can match a project equally well. Only one of them may fill a requirement your team cannot meet yet."],
            ["Rules first, ranking second", "Conditions you mark as mandatory filter the pool. Everything else only shifts the order, so nobody is silently excluded."],
            ["Every rank is explained", "You see which requirements a candidate would cover, which remain open, role fit and shared weekly slots — from their profile, nothing invented."],
          ].map(([t, d]) => (
            <div key={t}>
              <h2 className="font-semibold">{t}</h2>
              <p className="mt-2 text-sm text-ink-soft">{d}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
