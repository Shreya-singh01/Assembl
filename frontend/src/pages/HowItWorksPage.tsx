const features = [
  ["Semantic relevance", "0.30", "Cosine similarity between your profile text and the project text, from a pretrained Sentence-BERT model (all-MiniLM-L6-v2). Shows topical relatedness only — not skill level or fit."],
  ["Skill-gap contribution", "0.35", "How much of the team's remaining requirement gap you would close: the change in importance-weighted coverage if you joined, divided by what is still missing."],
  ["Vacant-role fit", "0.15", "1 if a vacant role is your primary preference, 0.5 if secondary, 0 otherwise."],
  ["Shared availability", "0.10", "Weekly slots you share with the team, relative to the minimum the team asked for. Unstated availability counts as a neutral 0.5 and is flagged."],
  ["Commitment & working mode", "0.10", "How close your expected weekly hours are to the team's, averaged with working-mode compatibility (hybrid fits both)."],
];

export function HowItWorksPage() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-3xl font-semibold">How Assembl ranks candidates</h1>
      <p className="mt-4 text-ink-soft">
        Assembl implements the method described in <em>“Assembl: Team-Aware Candidate Recommendation Using Semantic Skill Matching and Complementarity.”</em> It
        ranks students from the point of view of one team, as that team currently stands.
      </p>

      <h2 className="mt-10 text-xl font-semibold">1. Mandatory rules filter the pool</h2>
      <p className="mt-2 text-sm text-ink-soft">
        Before anything is scored, students are removed if their profile is hidden, they are already on the team or on another team for the same event, or they
        fail a rule the team creator marked as mandatory (allowed years, a required skill at the desired level, a vacant role, a minimum of shared weekly slots).
        If a rule cannot be checked because the profile leaves that field blank, it is recorded as <strong>unverified</strong>, not failed; the creator chooses
        whether unverified students are excluded or shown with a flag.
      </p>

      <h2 className="mt-8 text-xl font-semibold">2. Team coverage</h2>
      <p className="mt-2 text-sm text-ink-soft">
        For each required skill, coverage is the strongest current member's stated proficiency divided by the desired level (capped at 100%). Overall coverage is
        the average weighted by importance (useful = 1, important = 2, essential = 3). This uses one member per skill and does not model workload or the need for
        two specialists in the same area.
      </p>

      <h2 className="mt-8 text-xl font-semibold">3. Five signals, one transparent score</h2>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-ink-soft">
            <tr className="border-b border-line">
              <th className="py-2 pr-4 font-medium">Signal</th>
              <th className="py-2 pr-4 font-medium">Initial weight</th>
              <th className="py-2 font-medium">What it measures</th>
            </tr>
          </thead>
          <tbody>
            {features.map(([n, w, d]) => (
              <tr key={n} className="border-b border-line align-top">
                <td className="py-2 pr-4 font-medium">{n}</td>
                <td className="num py-2 pr-4">{w}</td>
                <td className="py-2 text-ink-soft">{d}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-sm text-ink-soft">
        The score is the weighted sum. When a signal does not apply to a request — the team already covers every requirement, works asynchronously, has no vacant
        role, or states no hours or mode — it is dropped and its weight is shared proportionally among the others. The weights are the paper's initial design
        choices; they have not been calibrated on real student judgments yet.
      </p>

      <h2 className="mt-8 text-xl font-semibold">What the score is not</h2>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-soft">
        <li>It is a relative ranking value for one team's request, not a probability that a team will succeed.</li>
        <li>Proficiency is self-reported and may be over- or under-stated.</li>
        <li>Names, e-mail addresses and demographic information are never used for ranking.</li>
        <li>A good match on paper is not evidence that people will collaborate well. The team decides whom to invite.</li>
      </ul>
    </article>
  );
}
