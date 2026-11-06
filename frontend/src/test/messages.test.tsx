import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Message } from "../api/types";
import { MessageBubble } from "../features/messaging/MessageBubble";

const msg = (over: Partial<Message> = {}): Message => ({
  id: "m1", conversation_id: "c1", sender_id: "u1", body: "helo", created_at: "2026-11-01T10:00:00Z", client_id: "cid12345", ...over,
});

describe("MessageBubble", () => {
  it("lets the sender edit their own message", async () => {
    const onEdit = vi.fn().mockResolvedValue(undefined);
    render(<MessageBubble m={msg()} mine onEdit={onEdit} onDelete={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Edit message" }));
    const box = screen.getByLabelText("Edit message", { selector: "textarea" });
    await userEvent.clear(box);
    await userEvent.type(box, "hello");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onEdit).toHaveBeenCalledWith("hello");
  });

  it("asks for confirmation before deleting", async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(<MessageBubble m={msg()} mine onEdit={vi.fn()} onDelete={onDelete} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete message" }));
    expect(onDelete).not.toHaveBeenCalled();
    expect(screen.getByText("Delete this message for everyone?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onDelete).toHaveBeenCalled();
  });

  it("offers no controls on other people's messages and shows edited/deleted states", () => {
    const { rerender } = render(<MessageBubble m={msg({ edited_at: "2026-11-01T10:05:00Z" })} mine={false} onEdit={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Edit message" })).not.toBeInTheDocument();
    expect(screen.getByText("· edited")).toBeInTheDocument();
    rerender(<MessageBubble m={msg({ deleted: true, body: "" })} mine onEdit={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText("Message deleted")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit message" })).not.toBeInTheDocument();
  });
});
