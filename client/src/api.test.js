import { afterEach, describe, expect, it } from "vitest";
import { setStudyTicket, speechUrl } from "./api.js";

describe("speechUrl", () => {
  afterEach(() => setStudyTicket(null));

  it("asks for one spoken line", () => {
    expect(speechUrl("Try it. Then run?")).toBe("/v1/tts?text=Try+it.+Then+run%3F");
  });

  it("carries a study student's ticket, since the tutor's player can't set headers", () => {
    setStudyTicket("abc.123");
    expect(speechUrl("Hi")).toBe("/v1/tts?text=Hi&ticket=abc.123");
  });
});
