import { useEffect, useRef, useState } from "react";
import { speechUrl } from "./api.js";

// The 3D tutor beside the chat panel: the Unity page in /avatar/ renders only the character,
// transparent over the coding environment, and says each reply with lip-sync and gestures. The
// words are all in the chat, so it is hidden from assistive tech.

export const BUILD_PROBE = "/avatar/build/build.json";

// Whether a Unity build is installed. A site without one may answer any path with its own page.
export async function avatarInstalled(fetchImpl = fetch) {
  try {
    const response = await fetchImpl(`${BUILD_PROBE}?t=${Date.now()}`, { cache: "no-store" });
    return response.ok && Boolean(await response.json());
  } catch {
    return false;
  }
}

// Beside the panel the whole character shows. A phone has no room beside the sheet, so there
// the tutor's head and shoulders sit in the left end of the sheet's (or the note's) title bar,
// the head just over its edge, and never stand on the code.
export const FULL_BODY = 1;
export const HEAD_AND_SHOULDERS = 0.42;
const PHONE = 671;
const EDGE = 8;

export function placeAvatar(panel, viewport) {
  if (viewport.width <= PHONE) {
    return {
      framing: HEAD_AND_SHOULDERS,
      box: { width: 64, height: 80, left: panel.left + 8, top: panel.top - 26 },
    };
  }
  const height = Math.round(Math.min(460, Math.max(280, panel.height * 0.72)));
  const width = Math.round(height * 0.44);
  const tuck = Math.round(width * 0.12); // a little behind the panel, as if standing at it
  const left = panel.left - width + tuck;
  return {
    framing: FULL_BODY,
    box: {
      width,
      height,
      top: panel.bottom - height,
      left: left >= EDGE ? left : Math.min(panel.right - tuck, viewport.width - width - EDGE),
    },
  };
}

export default function Avatar({ panel, visible, utterance, muted, hush }) {
  // visible: signed in, the chat open and the student wants the tutor. Hidden, Unity pauses.
  const frame = useRef(null);
  const said = useRef(new Set());
  const framingSent = useRef(null);
  const [ready, setReady] = useState(false);
  const placement = panel
    ? placeAvatar(panel, { width: window.innerWidth, height: window.innerHeight })
    : null;

  useEffect(() => {
    const listen = (event) => {
      if (event.origin !== window.location.origin || event.source !== frame.current?.contentWindow)
        return;
      if (event.data?.type === "avatar-ready") {
        framingSent.current = null;
        setReady(true);
      }
    };
    window.addEventListener("message", listen);
    return () => window.removeEventListener("message", listen);
  }, []);

  const post = (message) =>
    frame.current?.contentWindow?.postMessage(message, window.location.origin);

  useEffect(() => {
    if (ready && placement && framingSent.current !== placement.framing) {
      framingSent.current = placement.framing;
      post({ type: "framing", framing: placement.framing });
    }
  });

  const shown = Boolean(visible && ready && placement);
  useEffect(() => {
    if (ready) post({ type: shown ? "resume" : "pause" });
  }, [ready, shown]);

  // Muting, or the student starting to speak, stops the voice at once.
  useEffect(() => {
    if (ready && (muted || hush)) post({ type: "hush" });
  }, [ready, muted, hush]);

  // Each reply is said once, however often the page renders. One that arrives while the tutor
  // is hidden is not said later.
  useEffect(() => {
    if (!ready || !utterance || said.current.has(utterance.id)) return;
    said.current.add(utterance.id);
    if (!shown) return;
    // One clip per sentence (the server's split), so the first plays while the rest are made.
    // Muted, the character still gestures.
    post({
      type: "speak",
      text: utterance.text,
      audios: muted ? [] : utterance.parts.map(speechUrl),
    });
  }, [ready, utterance, muted, shown]);

  return (
    <div
      className={`avatar ${shown ? "avatar--shown" : ""}`}
      aria-hidden="true"
      style={placement ? placement.box : undefined}
    >
      <iframe
        ref={frame}
        src={`/avatar/?framing=${FULL_BODY}`}
        title="INVITE Agent tutor"
        tabIndex={-1}
        allow="autoplay"
      />
    </div>
  );
}
