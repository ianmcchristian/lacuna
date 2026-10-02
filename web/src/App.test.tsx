import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { Scan } from "./api";

const scan: Scan = {
  id: "scan1",
  image_id: "img1",
  model: "sku110k-yolo11-s640",
  product_count: 20,
  gap_count: 1,
  occupancy: 0.91,
  latency_ms: 74.2,
  created_at: "2026-10-02T21:55:43Z",
  gaps: [{ row: 0, x1: 120, y1: 0, x2: 290, y2: 210, width_ratio: 1.8 }],
};

// jsdom can't do layout, so color contrast is checked in a real browser instead
async function expectNoA11yViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
}

function mockApi(...responses: Array<{ status: number; body: unknown }>) {
  const fetchMock = vi.fn();
  for (const { status, body } of responses) {
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(body), { status }));
  }
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const photo = () => new File(["fake"], "shelf.jpg", { type: "image/jpeg" });

afterEach(() => vi.unstubAllGlobals());

describe("App", () => {
  it("has labelled inputs and no axe violations", async () => {
    const { container } = render(<App />);
    expect(screen.getByLabelText("Shelf photo")).toBeInTheDocument();
    expect(screen.getByLabelText("Shelf code (optional)")).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("works with the keyboard alone", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.tab();
    expect(screen.getByText("Skip to content")).toHaveFocus();
    await user.tab();
    expect(screen.getByLabelText("Shelf photo")).toHaveFocus();
    await user.tab();
    expect(screen.getByLabelText("Shelf code (optional)")).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Scan shelf" })).toHaveFocus();
  });

  it("explains a missing photo and focuses the field", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Scan shelf" }));

    const input = screen.getByLabelText("Shelf photo");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(/Choose a shelf photo/);
    expect(input).toHaveFocus();
  });

  it("rejects a non-image before uploading", async () => {
    const fetchMock = mockApi();
    const user = userEvent.setup({ applyAccept: false });
    render(<App />);
    await user.upload(screen.getByLabelText("Shelf photo"), new File(["%PDF"], "a.pdf", { type: "application/pdf" }));
    await user.click(screen.getByRole("button", { name: "Scan shelf" }));

    expect(screen.getByText("Use a JPEG, PNG, or WebP image.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows results, moves focus to them, and stays accessible", async () => {
    const fetchMock = mockApi({ status: 201, body: { id: "img1" } }, { status: 201, body: scan });
    const user = userEvent.setup();
    const { container } = render(<App />);

    await user.upload(screen.getByLabelText("Shelf photo"), photo());
    await user.type(screen.getByLabelText("Shelf code (optional)"), "aisle4-bay2");
    await user.click(screen.getByRole("button", { name: "Scan shelf" }));

    const heading = await screen.findByRole("heading", { name: "Results" });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(screen.getByText("91%")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAccessibleName(/20 products .* 1 gap shaded red/);
    expect(screen.getByRole("table", { name: /Gaps by shelf row/ })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await expectNoA11yViolations(container);
  });

  it("announces API errors", async () => {
    mockApi({ status: 413, body: { detail: "file is over the 10 MB limit" } });
    const user = userEvent.setup();
    render(<App />);
    await user.upload(screen.getByLabelText("Shelf photo"), photo());
    await user.click(screen.getByRole("button", { name: "Scan shelf" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("file is over the 10 MB limit");
  });
});
