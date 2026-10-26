import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { CoverageChart } from "../features/recommendations/CoverageChart";
import { CandidateCard } from "../features/recommendations/CandidateCard";
import { compareCandidates } from "../features/recommendations/compare";
import { AvailabilityGrid } from "../features/profiles/AvailabilityGrid";
import { MetricsTable } from "../features/research/ResearchPage";
import { candidate, LABELS, recommendations } from "./fixtures";

describe("compareCandidates", () => {
  it("orders features by absolute contribution difference", () => {
    const a = candidate({ id: "a", name: "Bea", score: 0.85, contributions: { sem: 0.2, gap: 0.45, role: 0.2 } });
    const b = candidate({ id: "b", name: "Fred", score: 0.34, contributions: { sem: 0.34, gap: 0, role: 0 } });
    const { total, diffs } = compareCandidates(a, b);
    expect(total).toBeCloseTo(0.51);
    expect(diffs.map((d) => d.feature)).toEqual(["gap", "role", "sem"]);
    expect(diffs[0].diff).toBeCloseTo(0.45);
    expect(diffs[2].diff).toBeCloseTo(-0.14);
  });
});

describe("CoverageChart", () => {
  it("renders the computed values, not decoration", () => {
    render(<CoverageChart coverage={recommendations([]).team_coverage} />);
    expect(screen.getByText("40%")).toBeInTheDocument();
    const meter = screen.getByRole("meter", { name: "Node.js coverage" });
    expect(meter).toHaveAttribute("aria-valuenow", "0");
    expect(screen.getByRole("meter", { name: "React coverage" })).toHaveAttribute("aria-valuenow", "1");
  });

  it("previews a candidate's added coverage", () => {
    render(<CoverageChart coverage={recommendations([]).team_coverage} highlight={{ "Node.js": 1 }} />);
    expect(screen.getByText("→ 100%")).toBeInTheDocument();
  });
});

describe("CandidateCard", () => {
  it("shows the ranking score as a relative value and expands the explanation", async () => {
    const c = candidate({ id: "a", name: "Bea", score: 0.85, contributions: { sem: 0.2, gap: 0.45, role: 0.2 } });
    const onInvite = vi.fn().mockResolvedValue(undefined);
    render(
      <MemoryRouter>
        <CandidateCard c={c} labels={{ ...LABELS }} vacantRoles={["Backend"]} canInvite selected={false} onSelect={() => {}} onInvite={onInvite} />
      </MemoryRouter>,
    );
    expect(screen.getByText("0.85")).toHaveAttribute("title", expect.stringContaining("not a probability"));
    expect(screen.queryByText(/%\s*chance|probability of success/i)).not.toBeInTheDocument();
    expect(screen.getByText(/\+ Node\.js 3\/4/)).toBeInTheDocument();

    const toggle = screen.getByRole("button", { name: "Why this rank?" });
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const table = screen.getByRole("table");
    expect(within(table).getByText("Ranking score")).toBeInTheDocument();
    expect(within(table).getAllByText("not used for this request")).toHaveLength(2);

    await userEvent.click(screen.getByRole("button", { name: "Invite" }));
    expect(onInvite).toHaveBeenCalledWith("Backend");
  });

  it("hides the invite action when an invitation is pending", () => {
    const c = candidate({ id: "a", name: "Bea", score: 0.5, contributions: { sem: 0.5 }, invitation_status: "pending" });
    render(
      <MemoryRouter>
        <CandidateCard c={c} labels={{ ...LABELS }} vacantRoles={[]} canInvite selected={false} onSelect={() => {}} onInvite={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("button", { name: "Invite" })).not.toBeInTheDocument();
    expect(screen.getByText("Invitation pending")).toBeInTheDocument();
  });
});

describe("AvailabilityGrid", () => {
  it("keeps 'not stated' distinct from an empty selection and is keyboard operable", async () => {
    const onChange = vi.fn();
    const { rerender } = render(<AvailabilityGrid value={null} onChange={onChange} />);
    expect(screen.getByText(/never treated as “unavailable”/)).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText(/mark the times/));
    expect(onChange).toHaveBeenLastCalledWith([]);

    rerender(<AvailabilityGrid value={[]} onChange={onChange} />);
    const cell = screen.getByRole("button", { name: "Mon evening" });
    cell.focus();
    await userEvent.keyboard("{Enter}");
    expect(onChange).toHaveBeenLastCalledWith(["mon-eve"]);
  });
});

describe("MetricsTable", () => {
  it("prints 'not measured' instead of numbers for unmeasured metrics", () => {
    const nm = { value: null, n: 0, status: "not measured" as const };
    render(
      <MetricsTable
        rows={{
          M5: {
            "ndcg@5": nm,
            "precision@5": nm,
            "added_coverage@5": { value: 0.15, n: 15, status: "measured" },
            "constraint_violations@5": { value: 0.2, n: 15, status: "measured" },
            mandatory_violations: 0,
          },
        }}
      />,
    );
    expect(screen.getAllByText("not measured")).toHaveLength(2);
    expect(screen.getByText("0.150")).toBeInTheDocument();
    expect(screen.getByText("20.0%")).toBeInTheDocument();
  });
});
