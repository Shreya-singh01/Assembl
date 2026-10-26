import { expect, test, type Page } from "@playwright/test";

const DEMO_PASSWORD = "demo-password-123";
const shots = process.env.E2E_SCREENSHOTS; // directory for review screenshots (optional)

async function snap(page: Page, name: string) {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}

test("register, build a profile, create a team, invite, accept, chat", async ({ browser }) => {
  const stamp = Date.now().toString().slice(-6);
  const owner = await (await browser.newContext()).newPage();

  // --- register + onboarding --------------------------------------------
  await owner.goto("/");
  await snap(owner, "01-landing");
  await owner.getByRole("link", { name: "Create an account" }).click();
  await owner.getByLabel("Display name").fill("Priya E2E");
  await owner.getByLabel("Handle").fill(`priya_${stamp}`);
  await owner.getByLabel("E-mail").fill(`priya_${stamp}@example.edu`);
  await owner.getByLabel("Password").fill("a-long-password-1");
  await owner.getByRole("checkbox").check();
  await owner.getByRole("button", { name: "Create account" }).click();
  await expect(owner.getByRole("heading", { name: "Set up your profile" })).toBeVisible();

  await owner.getByRole("button", { name: "+ Add skill" }).click();
  await owner.getByLabel("Skill 1", { exact: true }).fill("reactjs");
  await owner.getByLabel("Proficiency for skill 1").selectOption("3");
  await owner.getByRole("button", { name: "+ Add skill" }).click();
  await owner.getByLabel("Skill 2", { exact: true }).fill("Machine Learning");
  await owner.getByLabel("Proficiency for skill 2").selectOption("3");
  await owner.getByLabel("Primary roles").fill("Frontend");
  await owner.getByLabel("Primary roles").press("Enter");
  await owner.getByLabel("I'll mark the times I'm usually free").check();
  await owner.getByRole("button", { name: "Mon evening" }).click();
  await owner.getByRole("button", { name: "Wed evening" }).click();
  await snap(owner, "02-profile");
  await owner.getByRole("button", { name: "Save and continue" }).click();
  await expect(owner.getByRole("heading", { name: /Hello, Priya E2E/ })).toBeVisible();
  await snap(owner, "03-dashboard");

  // --- create a team ------------------------------------------------------
  await owner.getByRole("link", { name: "Start a team" }).first().click();
  await owner.getByLabel("Title").fill(`Campus placement prep ${stamp}`);
  await owner.getByLabel("Description").fill("A web app with mock interviews, aptitude tests and analytics to help students prepare for placements.");
  await owner.getByRole("button", { name: "Continue" }).click();
  const skills = [
    ["React", "2", "3"],
    ["nodejs", "3", "3"],
    ["postgres", "3", "2"],
  ];
  for (let i = 0; i < skills.length; i++) {
    if (i > 0) await owner.getByRole("button", { name: "+ Add skill" }).click();
    await owner.getByLabel(`Skill ${i + 1}`, { exact: true }).fill(skills[i][0]);
    await owner.getByLabel(`Importance of skill ${i + 1}`).selectOption(skills[i][1]);
    await owner.getByLabel(`Desired level for skill ${i + 1}`).selectOption(skills[i][2]);
  }
  await owner.getByRole("button", { name: "Continue" }).click();
  await owner.getByLabel("Target team size").fill("3");
  await owner.getByLabel("Your role in the team (optional)").fill("Frontend");
  await owner.getByLabel("Vacant roles").fill("Backend");
  await owner.getByLabel("Vacant roles").press("Enter");
  await owner.getByRole("button", { name: "Continue" }).click();
  await owner.getByRole("button", { name: "Continue" }).click();
  await snap(owner, "04-wizard-review");
  await owner.getByRole("button", { name: "Create and see candidates" }).click();

  // --- recommendations ------------------------------------------------------
  await expect(owner.getByRole("heading", { name: `Find members for Campus placement prep ${stamp}` })).toBeVisible();
  // first request after a cold start encodes every profile; later requests use cached embeddings
  await expect(owner.getByText("Importance-weighted coverage")).toBeVisible({ timeout: 30_000 });
  const firstCard = owner.locator("article").first();
  await expect(firstCard).toBeVisible({ timeout: 30_000 });
  await expect(firstCard.getByText(/Proficiency is self-reported\./)).toBeVisible();
  await firstCard.getByRole("button", { name: "Why this rank?" }).click();
  await expect(firstCard.getByRole("table")).toContainText("Ranking score");
  await snap(owner, "05-recommendations");
  const handle = ((await firstCard.locator("h3 span").first().textContent()) ?? "").replace("@", "").trim();
  expect(handle).toMatch(/_demo\d+$/);
  await firstCard.getByRole("button", { name: "Invite" }).click();
  await expect(owner.getByText(/Invitation sent to/)).toBeVisible();

  // --- the invited demo student accepts -------------------------------------
  const cand = await (await browser.newContext()).newPage();
  await cand.goto("/login");
  await cand.getByLabel("E-mail").fill(`${handle}@demo.assembl.example`);
  await cand.getByLabel("Password").fill(DEMO_PASSWORD);
  await cand.getByRole("button", { name: "Sign in" }).click();
  await expect(cand.getByRole("heading", { name: /Hello/ })).toBeVisible();
  await cand.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Invitations" }).click();
  const row = cand.getByRole("listitem").filter({ hasText: `Campus placement prep ${stamp}` });
  await expect(row.getByText(/invited you to join/)).toBeVisible();
  await snap(cand, "06-invitations");
  await row.getByRole("button", { name: "Accept" }).click();
  await expect(row.getByText("accepted")).toBeVisible();

  // owner sees the team update and a refreshed ranking
  await owner.goto(owner.url().replace("/recommendations", ""));
  await expect(owner.getByRole("heading", { name: /Team \(2\/3\)/ })).toBeVisible();
  await snap(owner, "07-project");

  // --- team chat in real time -----------------------------------------------
  await owner.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Messages" }).click();
  await owner.getByRole("link", { name: new RegExp(`Team: Campus placement prep ${stamp}`) }).click();
  await cand.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Messages" }).click();
  await cand.getByRole("link", { name: new RegExp(`Team: Campus placement prep ${stamp}`) }).click();
  await expect(cand.getByLabel("Live updates connected")).toBeVisible({ timeout: 15_000 });
  await owner.getByLabel("Message", { exact: true }).fill("Welcome aboard! Can you own the API?");
  await owner.getByRole("button", { name: "Send" }).click();
  await expect(cand.getByText("Welcome aboard! Can you own the API?")).toBeVisible({ timeout: 10_000 });
  await snap(cand, "08-messages");

  // --- transparency page + research status ------------------------------------
  await owner.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Research" }).click();
  await expect(owner.getByText("Evaluation pending")).toBeVisible();
  await snap(owner, "09-research");
});

test("mobile layout has no horizontal overflow on key pages", async ({ browser }) => {
  const page = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
  for (const path of ["/", "/login", "/how-it-works"]) {
    await page.goto(path);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
  await snap(page, "10-mobile-landing");
});
