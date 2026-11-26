import { useEffect, useRef, useState } from "react";

// The chat floats over the coding environment: dragged by its header, resized from any corner.
// While it moves, the frame underneath ignores the pointer, or it would swallow the drag. It is
// dressed as a ZANY window: a VEX-blue title bar, then a light-blue tool bar.

export const MIN_WIDTH = 360;
// The agent's tab on the right edge (app.css .edge-tab). The window opens just left of it.
const TAB = 40;
// VEXcode VR's and ZANY's own bars take about the top 110px. The window opens below them, so
// their buttons stay in reach.
const TOOLBARS = 120;
const SHORT = 720;
export const MIN_HEIGHT = 360;
const EDGE = 12;
const CORNERS = ["nw", "ne", "sw", "se"];

export const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

export function defaultRect(viewport = { width: window.innerWidth, height: window.innerHeight }) {
  const width = 400;
  // On a short window, such as a Chromebook's, it takes at most 60% of the height.
  const height = clamp(
    Math.min(620, Math.round(viewport.height * 0.6)),
    MIN_HEIGHT,
    viewport.height - TOOLBARS - 24,
  );
  return {
    x: Math.max(EDGE, viewport.width - width - TAB - EDGE),
    // A short window opens it right under the bars instead, so the playground's Start, Reset
    // and Step row along the bottom stays free.
    y: viewport.height < SHORT ? TOOLBARS : Math.max(EDGE, viewport.height - height - 24),
    width,
    height,
  };
}

// The rect after dragging `corner` by (dx, dy) from `start`, kept on screen and above the minimum.
export function resized(start, corner, dx, dy, viewport) {
  const right = start.x + start.width;
  const bottom = start.y + start.height;
  let { x, y, width, height } = start;
  if (corner.includes("e")) width = clamp(start.width + dx, MIN_WIDTH, viewport.width - x - EDGE);
  if (corner.includes("w")) {
    width = clamp(start.width - dx, MIN_WIDTH, right - EDGE);
    x = right - width;
  }
  if (corner.includes("s"))
    height = clamp(start.height + dy, MIN_HEIGHT, viewport.height - y - EDGE);
  if (corner.includes("n")) {
    height = clamp(start.height - dy, MIN_HEIGHT, bottom - EDGE);
    y = bottom - height;
  }
  return { x, y, width, height };
}

export default function Panel({
  label,
  header,
  toolbar,
  footer,
  children,
  resizable,
  onMoving,
  onRect,
}) {
  const [rect, setRect] = useState(defaultRect);
  const gesture = useRef(null);

  const element = useRef(null);

  // Report the box the panel really has on screen (on a phone, CSS makes it a bottom sheet),
  // after every move, every change of its content and every window resize.
  useEffect(() => {
    const report = () => {
      const box = element.current?.getBoundingClientRect();
      if (box) onRect?.(box);
    };
    report();
    window.addEventListener("resize", report);
    const observer = "ResizeObserver" in window ? new ResizeObserver(report) : null;
    if (element.current) observer?.observe(element.current);
    return () => {
      window.removeEventListener("resize", report);
      observer?.disconnect();
    };
  }, [rect, resizable, onRect]);

  // A smaller window pulls the panel back on screen.
  useEffect(() => {
    const fit = () =>
      setRect((r) => {
        const width = Math.min(r.width, Math.max(MIN_WIDTH, window.innerWidth - 2 * EDGE));
        const height = Math.min(r.height, Math.max(MIN_HEIGHT, window.innerHeight - 2 * EDGE));
        return {
          width,
          height,
          x: clamp(r.x, EDGE, Math.max(EDGE, window.innerWidth - width - EDGE)),
          y: clamp(r.y, EDGE, Math.max(EDGE, window.innerHeight - height - EDGE)),
        };
      });
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);

  const begin = (event, kind, corner) => {
    if (kind === "drag" && event.target.closest("button, input, textarea, select, a")) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    gesture.current = { kind, corner, x: event.clientX, y: event.clientY, start: rect };
    onMoving?.(true);
  };

  const move = (event) => {
    const g = gesture.current;
    if (!g) return;
    const dx = event.clientX - g.x;
    const dy = event.clientY - g.y;
    const viewport = { width: window.innerWidth, height: window.innerHeight };
    if (g.kind === "drag") {
      setRect({
        ...g.start,
        x: clamp(g.start.x + dx, EDGE, viewport.width - g.start.width - EDGE),
        y: clamp(g.start.y + dy, EDGE, viewport.height - 64),
      });
    } else {
      setRect(resized(g.start, g.corner, dx, dy, viewport));
    }
  };

  const end = () => {
    if (!gesture.current) return;
    gesture.current = null;
    onMoving?.(false);
  };

  return (
    <section
      ref={element}
      className="agent-panel"
      aria-label={label}
      style={
        resizable
          ? { left: rect.x, top: rect.y, width: rect.width, height: rect.height }
          : { left: rect.x, width: rect.width, bottom: window.innerHeight - rect.y - rect.height }
      }
      onPointerMove={move}
      onPointerUp={end}
      onPointerCancel={end}
      onLostPointerCapture={end}
    >
      <header className="agent-panel__header" onPointerDown={(e) => begin(e, "drag")}>
        {header}
      </header>
      {toolbar ? <div className="agent-panel__toolbar">{toolbar}</div> : null}
      <div className="agent-panel__body">{children}</div>
      {footer ? <footer className="agent-panel__footer">{footer}</footer> : null}
      {resizable
        ? CORNERS.map((corner) => (
            <span
              key={corner}
              aria-hidden="true"
              className={`agent-panel__corner agent-panel__corner--${corner}`}
              onPointerDown={(e) => begin(e, "resize", corner)}
            />
          ))
        : null}
    </section>
  );
}
