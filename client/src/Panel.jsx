import { useEffect, useRef, useState } from "react";
import { Layer } from "@carbon/react";

// The chat floats over the coding environment: dragged by its header, resized from any corner.
// While it moves, the frame underneath ignores the pointer, or it would swallow the drag. Its
// body is a Carbon Layer over the panel, so fields and tiles take the next layer's colours.

export const MIN_WIDTH = 360;
export const MIN_HEIGHT = 480;
const EDGE = 12;
const CORNERS = ["nw", "ne", "sw", "se"];

export const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

export function defaultRect(viewport = { width: window.innerWidth, height: window.innerHeight }) {
  const width = 420;
  const height = clamp(640, MIN_HEIGHT, viewport.height - 2 * 24);
  return {
    x: Math.max(EDGE, viewport.width - width - 24),
    y: Math.max(EDGE, viewport.height - height - 24),
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

export default function Panel({ label, header, footer, children, resizable, onMoving, onRect }) {
  const [rect, setRect] = useState(defaultRect);
  const gesture = useRef(null);

  useEffect(() => onRect?.(rect), [rect, onRect]);

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
      <Layer className="agent-panel__body">{children}</Layer>
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
