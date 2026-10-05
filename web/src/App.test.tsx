import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import * as browserScan from "./inference/browserScan";
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

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// pretend this is a browser that can run the model
function canRunInBrowser() {
  vi.stubGlobal("OffscreenCanvas", class {});
  vi.stubGlobal("createImageBitmap", vi.fn());
  // jsdom has no blob URLs at all
  Object.assign(URL, { createObjectURL: vi.fn(() => "blob:overlay"), revokeObjectURL: vi.fn() });
}

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
    expect(screen.getByRole("link", { name: "Scan a shelf" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: "Shelf history" })).toHaveFocus();
    await user.tab(); // jsdom can't run the model, so the server is the only choice
    expect(screen.getByRole("radio", { name: "On the server" })).toHaveFocus();
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

  it("clears the error once a photo is chosen", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Scan shelf" }));
    await user.upload(screen.getByLabelText("Shelf photo"), photo());

    expect(screen.queryByText("Choose a shelf photo.")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Shelf photo")).not.toHaveAttribute("aria-invalid");
  });

  it("doesn't call an unreadable photo fully stocked", async () => {
    const empty = { ...scan, product_count: 0, gap_count: 0, occupancy: null, gaps: [] };
    mockApi({ status: 201, body: { id: "img1" } }, { status: 201, body: empty });
    const user = userEvent.setup();
    render(<App />);
    await user.upload(screen.getByLabelText("Shelf photo"), photo());
    await user.click(screen.getByRole("button", { name: "Scan shelf" }));

    expect(await screen.findByText(/Not enough products found/)).toBeInTheDocument();
    expect(screen.queryByText(/fully stocked/)).not.toBeInTheDocument();
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
    expect(screen.getByRole("link", { name: "See the history for shelf aisle4-bay2" })).toHaveAttribute(
      "href",
      "#/shelves/aisle4-bay2",
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await expectNoA11yViolations(container);
  });

  it("scans a sample shelf in one click", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("jpeg bytes", { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "img1" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(scan), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const { container } = render(<App />);

    await user.click(screen.getByRole("button", { name: /^Depleted 6 holes/ }));

    expect(await screen.findByRole("heading", { name: "Results" })).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toMatch(/samples\/depleted\.jpg$/);
    const upload = fetchMock.mock.calls[1][1].body as FormData;
    expect((upload.get("file") as File).name).toBe("depleted.jpg");
    await expectNoA11yViolations(container);
  });

  it("marks the known failures", () => {
    render(<App />);
    expect(screen.getAllByText("Hard case")).toHaveLength(3);
    expect(screen.getByRole("button", { name: /^Angled .* Hard case$/ })).toBeInTheDocument();
  });

  it("runs in the browser by default when it can, without the API", async () => {
    canRunInBrowser();
    const fetchMock = mockApi();
    const scanSpy = vi.spyOn(browserScan, "scanInBrowser").mockResolvedValue({
      model: "sku110k-yolo11-s640-int8",
      product_count: 20,
      gap_count: 1,
      occupancy: 0.91,
      latency_ms: 140,
      gaps: scan.gaps,
      overlay: new Blob(),
    });
    const user = userEvent.setup();
    const { container } = render(<App />);

    expect(screen.getByRole("radio", { name: "In this browser" })).toBeChecked();
    expect(screen.queryByLabelText("Shelf code (optional)")).not.toBeInTheDocument();
    await user.upload(screen.getByLabelText("Shelf photo"), photo());
    await user.click(screen.getByRole("button", { name: "Scan shelf" }));

    expect(await screen.findByText(/Ran in your browser/)).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAttribute("src", "blob:overlay");
    expect(screen.queryByRole("link", { name: /See the history/ })).not.toBeInTheDocument();
    expect(scanSpy).toHaveBeenCalledOnce();
    expect(fetchMock).not.toHaveBeenCalled();
    await expectNoA11yViolations(container);
  });

  it("suggests the server when the browser can't run the model", async () => {
    canRunInBrowser();
    vi.spyOn(browserScan, "scanInBrowser").mockRejectedValue(new Error("no wasm"));
    const user = userEvent.setup();
    render(<App />);
    await user.upload(screen.getByLabelText("Shelf photo"), photo());
    await user.click(screen.getByRole("button", { name: "Scan shelf" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Try running it on the server/);
  });

  it("asks for a shelf code only for server scans", async () => {
    canRunInBrowser();
    const user = userEvent.setup();
    render(<App />);
    expect(screen.queryByLabelText("Shelf code (optional)")).not.toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "On the server" }));
    expect(screen.getByLabelText("Shelf code (optional)")).toBeInTheDocument();
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
