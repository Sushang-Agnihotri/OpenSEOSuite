import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DataBadge, DataTable, Modal, Pagination, SeverityBadge, StatusCode, Tabs, type Column } from "../components/ui";
import { api, ApiError, tokenStore } from "../lib/api";
import { fmtBytes, fmtMs, fmtPct, scoreColor, shortUrl } from "../lib/format";

interface Row { id: number; name: string }
const rows: Row[] = [{ id: 1, name: "alpha" }, { id: 2, name: "beta" }];
const columns: Column<Row>[] = [
  { key: "id", header: "ID", render: (r) => r.id, sortKey: "id" },
  { key: "name", header: "Name", render: (r) => r.name },
];

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("DataTable", () => {
  it("renders rows and reports row clicks and sort requests", () => {
    const onRowClick = vi.fn();
    const onSort = vi.fn();
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} onRowClick={onRowClick} onSort={onSort} sort="id" order="desc" />);
    fireEvent.click(screen.getByText("beta"));
    expect(onRowClick).toHaveBeenCalledWith(rows[1]);
    fireEvent.click(screen.getByRole("button", { name: /ID/ }));
    expect(onSort).toHaveBeenCalledWith("id");
    expect(screen.getByText("↓")).toBeInTheDocument();
  });

  it("shows an empty state when there are no rows", () => {
    render(<DataTable columns={columns} rows={[]} rowKey={(r) => r.id} />);
    expect(screen.getByText("Nothing to show")).toBeInTheDocument();
  });
});

describe("Pagination", () => {
  it("disables previous on the first page and moves forward", () => {
    const onPage = vi.fn();
    render(<Pagination page={1} perPage={10} total={35} onPage={onPage} />);
    expect(screen.getByLabelText("Previous page")).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Next page"));
    expect(onPage).toHaveBeenCalledWith(2);
    expect(screen.getByText(/1–10 of 35/)).toBeInTheDocument();
  });

  it("shows only a row count when everything fits on one page", () => {
    render(<Pagination page={1} perPage={50} total={3} onPage={() => {}} />);
    expect(screen.getByText("3 rows")).toBeInTheDocument();
    expect(screen.queryByLabelText("Next page")).toBeNull();
  });
});

describe("badges", () => {
  it("renders severity, status codes and data provenance", () => {
    render(<><SeverityBadge severity="critical" /><StatusCode code={404} /><StatusCode code={null} error="timeout" /><DataBadge kind="estimated" /></>);
    expect(screen.getByText("critical")).toBeInTheDocument();
    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.getByText("error")).toHaveAttribute("title", "timeout");
    expect(screen.getByText("estimated").getAttribute("title")).toMatch(/estimate/i);
  });
});

describe("Tabs and Modal", () => {
  it("switches tabs", () => {
    const onChange = vi.fn();
    render(<Tabs tabs={[{ id: "a", label: "First" }, { id: "b", label: "Second", count: 4 }]} value="a" onChange={onChange} />);
    expect(screen.getByRole("tab", { name: "First" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: /Second/ }));
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("closes the modal on Escape and renders nothing when closed", () => {
    const onClose = vi.fn();
    const { rerender } = render(<Modal open title="Confirm" onClose={onClose}>body</Modal>);
    expect(screen.getByRole("dialog", { name: "Confirm" })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
    rerender(<Modal open={false} title="Confirm" onClose={onClose}>body</Modal>);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("format helpers", () => {
  it("formats sizes, durations, ratios and URLs", () => {
    expect(fmtBytes(512)).toBe("512 B");
    expect(fmtBytes(2048)).toBe("2.0 KB");
    expect(fmtBytes(null)).toBe("–");
    expect(fmtMs(850)).toBe("850 ms");
    expect(fmtMs(1500)).toBe("1.50 s");
    expect(fmtPct(0.1234)).toBe("12.3%");
    expect(shortUrl("https://example.com/a?b=1", "https://example.com/")).toBe("/a?b=1");
    expect(shortUrl("https://other.com/x", "https://example.com/")).toBe("other.com/x");
    expect(scoreColor(90)).not.toBe(scoreColor(40));
  });
});

describe("api client", () => {
  const respond = (status: number, body: unknown) =>
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));

  it("turns FastAPI validation errors into a readable message", async () => {
    respond(422, { detail: [{ loc: ["body", "url"], msg: "Field required" }, { loc: ["body", "name"], msg: "String too short" }] });
    await expect(api.post("/sites", {})).rejects.toMatchObject({ status: 422, message: "url: Field required; name: String too short" });
  });

  it("sends the bearer token and clears it on 401", async () => {
    tokenStore.set("abc");
    const spy = respond(401, { detail: "Invalid or expired token" });
    await expect(api.get("/sites")).rejects.toBeInstanceOf(ApiError);
    expect((spy.mock.calls[0][1] as RequestInit).headers).toMatchObject({ Authorization: "Bearer abc" });
    expect(tokenStore.get()).toBeNull();
  });

  it("omits empty query parameters", async () => {
    const spy = respond(200, { ok: true });
    await api.get("/crawls/1/pages", { q: "", status: "4xx", page: 2, kind: undefined });
    expect(spy.mock.calls[0][0]).toBe("/api/crawls/1/pages?status=4xx&page=2");
  });
});
