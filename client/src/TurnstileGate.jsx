import { useEffect, useRef, useState } from "react";
import { InlineLoading, InlineNotification } from "@carbon/react";

// The Cloudflare Turnstile challenge, full screen, shown when the API asks for it (api.js sends
// "turnstile:required"). Solving it sets the cookie, and the page reloads with it.
const SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || "0x4AAAAAAD9y1rcwgwx5PODV";

export default function TurnstileGate() {
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  const box = useRef(null);
  const widget = useRef(null);

  useEffect(() => {
    const show = () => setOpen(true);
    window.addEventListener("turnstile:required", show);
    return () => window.removeEventListener("turnstile:required", show);
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const render = () => {
      if (widget.current || !window.turnstile || !box.current) return;
      widget.current = window.turnstile.render(box.current, {
        sitekey: SITE_KEY,
        action: "agent",
        callback: async (token) => {
          const response = await fetch("/v1/turnstile/verify/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({ token }),
          }).catch(() => null);
          if (response?.ok) window.location.reload();
          else {
            setFailed(true);
            window.turnstile.reset(widget.current);
          }
        },
        "error-callback": () => setFailed(true),
      });
    };
    // Cloudflare's script loads async, so wait for it, for up to 15 seconds.
    let waited = 0;
    const timer = setInterval(() => {
      if (window.turnstile) {
        clearInterval(timer);
        render();
      } else if ((waited += 150) >= 15000) {
        clearInterval(timer);
        setFailed(true);
      }
    }, 150);
    render();
    return () => clearInterval(timer);
  }, [open]);

  if (!open) return null;
  return (
    <div className="turnstile-gate" role="dialog" aria-label="Checking you're not a bot">
      <InlineLoading description="Checking you're not a bot…" />
      <div ref={box} />
      {failed ? (
        <InlineNotification
          kind="error"
          title="That didn't work"
          subtitle="Reload the page to try again."
          lowContrast
          hideCloseButton
        />
      ) : null}
    </div>
  );
}
