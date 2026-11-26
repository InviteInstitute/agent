import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App.jsx";
import { renderInline } from "./Chat.jsx";
import { resized } from "./Panel.jsx";
import { describeOverrides, overridesFor, PRODUCTION_SETTINGS } from "./Research.jsx";

const VEX = {
  id: "vexcode-vr",
  name: "VEXcode VR",
  needs_class_code: false,
  frame: "https://vex.test/",
};
const ZANY = { id: "zany", name: "ZANY", needs_class_code: true, frame: null };

// A fake API: each route answers from `routes`, and every request is kept in `calls`.
function serve(routes) {
  const calls = [];
  global.fetch = vi.fn(async (url, init = {}) => {
    const u = new URL(url);
    const body = init.body ? JSON.parse(init.body) : undefined;
    calls.push({
      method: init.method || "GET",
      path: u.pathname,
      query: Object.fromEntries(u.searchParams),
      body,
    });
    const key = `${init.method || "GET"} ${u.pathname}`;
    const answer = typeof routes[key] === "function" ? routes[key](body, u) : routes[key];
    const [status, data] = answer ?? [404, { detail: "Not found" }];
    return { ok: status < 300, status, json: async () => data };
  });
  return calls;
}

const signedIn = (overrides = {}) => ({
  environment: "vexcode-vr",
  student_id: "S01",
  class_code: null,
  frame: "https://vex.test/",
  session_id: "abc",
  playground: "GO-Mars",
  messages: [],
  ...overrides,
});

beforeEach(() => {
  window.history.replaceState(null, "", "/");
  vi.stubGlobal("crypto", { randomUUID: () => Math.random().toString(36).slice(2) });
});
afterEach(() => vi.unstubAllGlobals());

describe("the agent page", () => {
  it("signs in, frames the environment and answers a question", async () => {
    const calls = serve({
      "GET /v1/ping": [200, { ok: true }],
      "GET /v1/environments": [200, { environments: [VEX], avatar: false }],
      "GET /v1/vexcode-vr/students/S01": [200, signedIn()],
      "PUT /v1/vexcode-vr/students/S01/settings": [204, null],
      "POST /v1/vexcode-vr/students/S01/turns": [
        200,
        {
          session_id: "abc",
          reply: { response_id: "r1", body: "Your `drive` block is loose." },
          session_tokens: { used: 10, limit: 100 },
        },
      ],
      "POST /v1/vexcode-vr/students/S01/ratings": [204, null],
    });
    const user = userEvent.setup();
    render(<App />);

    await user.type(await screen.findByLabelText("Student ID"), "S01");
    await user.click(screen.getByRole("button", { name: /Start chat/ }));
    expect(await screen.findByTitle("VEXcode VR")).toHaveAttribute("src", "https://vex.test/");

    await user.type(screen.getByLabelText("Message"), "why won't it move{Enter}");
    expect(await screen.findByText("drive")).toHaveClass("block-name");
    expect(calls.find((c) => c.path.endsWith("/turns")).body).toEqual({
      message: "why won't it move",
      overrides: null,
    });
    expect(JSON.parse(sessionStorage.getItem("agent:student")).studentId).toBe("S01");

    await user.click(screen.getByRole("button", { name: "This helped" }));
    await screen.findByText("Thanks!");
    expect(calls.find((c) => c.path.endsWith("/ratings")).body).toEqual({
      response_id: "r1",
      thumb: "up",
      comment: null,
    });
  });

  it("asks ZANY students for their class and frames ZANY only once they sign in", async () => {
    const calls = serve({
      "GET /v1/environments": [200, { environments: [VEX, ZANY], avatar: false }],
      "GET /v1/zany/students/S01": [
        200,
        signedIn({
          environment: "zany",
          class_code: "room-4",
          frame: "https://vr.test/?class=room-4&student=S01",
        }),
      ],
    });
    window.history.replaceState(null, "", "/?env=zany&class=room-4&student=S01");
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByLabelText("Class code")).toHaveValue("room-4");
    expect(screen.getByText("Your coding space opens here once you sign in.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Start chat/ }));
    expect(await screen.findByTitle("ZANY")).toHaveAttribute(
      "src",
      "https://vr.test/?class=room-4&student=S01",
    );
    expect(calls.find((c) => c.path === "/v1/zany/students/S01").query.class_code).toBe("room-4");
  });

  it("brings the chat back on reload", async () => {
    sessionStorage.setItem(
      "agent:student",
      JSON.stringify({ environment: "vexcode-vr", studentId: "S01", classCode: "" }),
    );
    serve({
      "GET /v1/environments": [200, { environments: [VEX], avatar: false }],
      "GET /v1/vexcode-vr/students/S01": [
        200,
        signedIn({
          messages: [
            {
              id: 1,
              role: "student",
              origin: "reactive",
              body: "help",
              response_id: null,
              thumb: null,
            },
            {
              id: 2,
              role: "agent",
              origin: "proactive",
              body: "Still there?",
              response_id: "r2",
              thumb: null,
            },
          ],
        }),
      ],
    });
    render(<App />);
    expect(await screen.findByText("Still there?")).toBeInTheDocument();
    expect(screen.getByText("Checking in")).toBeInTheDocument();
  });

  it("says plainly when the session is out of tokens", async () => {
    sessionStorage.setItem(
      "agent:student",
      JSON.stringify({ environment: "vexcode-vr", studentId: "S01", classCode: "" }),
    );
    serve({
      "GET /v1/environments": [200, { environments: [VEX], avatar: false }],
      "GET /v1/vexcode-vr/students/S01": [200, signedIn()],
      "POST /v1/vexcode-vr/students/S01/turns": [
        429,
        { detail: "This session has used its tokens." },
      ],
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Help" }));
    expect(await screen.findByText("This session has used its tokens.")).toBeInTheDocument();
  });

  it("shows the bot check when the API asks for it", async () => {
    serve({ "GET /v1/environments": [403, { error: "turnstile_required" }] });
    const seen = vi.fn();
    window.addEventListener("turnstile:required", seen);
    render(<App />);
    await waitFor(() => expect(seen).toHaveBeenCalled());
    window.removeEventListener("turnstile:required", seen);
  });
});

describe("pieces", () => {
  it("renders block names, bold and emphasis", () => {
    const parts = renderInline("Use `turn` then **stop** *now*.");
    expect(parts.map((p) => (typeof p === "string" ? p : p.type))).toEqual([
      "Use ",
      "code",
      " then ",
      "strong",
      " ",
      "em",
      ".",
    ]);
  });

  it("sends only the settings that differ from production", () => {
    const config = { defaults: { model: "qwen" }, prompt_template: "T" };
    expect(overridesFor(PRODUCTION_SETTINGS, config)).toBeNull();
    expect(
      overridesFor({ ...PRODUCTION_SETTINGS, model: "qwen", promptTemplate: "T" }, config),
    ).toBeNull();
    const custom = overridesFor(
      { ...PRODUCTION_SETTINGS, model: "gemma", temperature: 0, trimReply: false },
      config,
    );
    expect(custom).toEqual({ model: "gemma", temperature: 0, trim_reply: false });
    expect(describeOverrides(custom)).toBe("gemma, temperature 0, no trim");
  });

  it("resizes from a corner without going below the minimum or off screen", () => {
    const start = { x: 500, y: 200, width: 420, height: 600 };
    const viewport = { width: 1000, height: 900 };
    expect(resized(start, "nw", -100, -50, viewport)).toEqual({
      x: 400,
      y: 150,
      width: 520,
      height: 650,
    });
    expect(resized(start, "se", -500, 0, viewport).width).toBe(360);
    expect(resized(start, "se", 500, 500, viewport)).toEqual({
      x: 500,
      y: 200,
      width: 488,
      height: 688,
    });
  });
});

describe("check-ins", () => {
  it("shows a check-in the moment the server sends it, once", async () => {
    const sources = [];
    vi.stubGlobal(
      "EventSource",
      class {
        constructor(url) {
          this.url = String(url);
          this.listeners = {};
          sources.push(this);
        }
        addEventListener(name, listener) {
          this.listeners[name] = listener;
        }
        close() {
          this.closed = true;
        }
        send(data) {
          this.listeners.checkin({ data: JSON.stringify(data) });
        }
      },
    );
    sessionStorage.setItem(
      "agent:student",
      JSON.stringify({ environment: "zany", studentId: "S01", classCode: "room-4" }),
    );
    serve({
      "GET /v1/environments": [200, { environments: [VEX, ZANY], avatar: false }],
      "GET /v1/zany/students/S01": [200, signedIn({ environment: "zany", class_code: "room-4" })],
    });
    render(<App />);
    await screen.findByText(/Ask me about your project/);
    expect(sources[0].url).toContain("/v1/zany/students/S01/stream?class_code=room-4");

    const checkin = { id: 7, body: "Still there?", response_id: "r7", trigger_type: "inactive" };
    act(() => sources[0].send(checkin));
    act(() => sources[0].send(checkin));
    expect(await screen.findAllByText("Still there?")).toHaveLength(1);
    expect(screen.getByText("Checking in")).toBeInTheDocument();
  });
});
