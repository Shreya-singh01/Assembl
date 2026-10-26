export function PrivacyPage() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-10 text-sm">
      <h1 className="text-3xl font-semibold">Privacy and your data</h1>
      <h2 className="mt-8 text-lg font-semibold">What we collect and why</h2>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-soft">
        <li><strong>Account:</strong> e-mail, password (stored only as a salted scrypt hash), display name and handle — to sign you in and show who you are.</li>
        <li><strong>Profile:</strong> year, branch, skills with self-reported proficiency, preferred roles, interests, project summaries, weekly availability, expected hours and working mode — to rank you for teams and explain why.</li>
        <li><strong>Teams and messages:</strong> projects, invitations and messages you send — to run the service.</li>
      </ul>
      <p className="mt-2 text-ink-soft">We do not collect demographic information. Names, e-mails and contact details are never ranking inputs.</p>
      <h2 className="mt-8 text-lg font-semibold">Who sees what</h2>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-soft">
        <li>Your profile appears in recommendations only while “Show my profile to teams” is on.</li>
        <li>Teams see your skills, roles, interests, projects, hours and mode. They never see your weekly slots — only how many you share with them.</li>
        <li>Your e-mail address is never shown to other students.</li>
        <li>Messages are visible only to the people in the conversation.</li>
      </ul>
      <h2 className="mt-8 text-lg font-semibold">Research use</h2>
      <p className="mt-2 text-ink-soft">
        If you opt in to research participation, anonymised versions of profiles may be used in evaluation scenarios that student raters judge. Raters never see
        names, handles or contact details. Ratings are used only offline and never change live recommendations.
      </p>
      <h2 className="mt-8 text-lg font-semibold">Deleting your account</h2>
      <p className="mt-2 text-ink-soft">
        From Privacy &amp; account you can delete your account at any time. This permanently removes your account, sessions, profile and stored embeddings,
        invitations, the projects you created, your messages and your direct conversations, and frees your place on other teams.
      </p>
    </article>
  );
}
