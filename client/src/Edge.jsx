import { useCallback } from "react";
import { ChevronRight, MessageCircle, MessageCircleMore, X } from "lucide-react";
import { renderInline } from "./Chat.jsx";

// The agent at rest: a blue tab on the right edge of the screen. Its dot says whether the agent
// can see the student's code, and a badge counts replies they have not read.
export function EdgeTab({ open, seesCode, signedIn, unseen, onToggle }) {
  const label = open ? "Tuck the INVITE Agent away" : "Open the INVITE Agent";
  return (
    <button
      type="button"
      className={open ? "edge-tab edge-tab--open" : "edge-tab"}
      aria-expanded={open}
      aria-label={unseen ? `${label}, ${unseen} new` : label}
      title={label}
      onClick={onToggle}
    >
      {open ? (
        <ChevronRight size={22} strokeWidth={2.6} aria-hidden="true" />
      ) : (
        <MessageCircle size={22} strokeWidth={2.4} aria-hidden="true" />
      )}
      <span className="edge-tab__name" aria-hidden="true">
        Agent
      </span>
      {signedIn ? (
        <span
          className={seesCode ? "edge-tab__dot edge-tab__dot--seen" : "edge-tab__dot"}
          aria-hidden="true"
        />
      ) : null}
      {unseen && !open ? (
        <span className="edge-tab__count" aria-hidden="true">
          {unseen}
        </span>
      ) : null}
    </button>
  );
}

// A check-in that arrives while the chat is tucked away slides out of the tab as a note, in the
// gold of ZANY's playground window. The student replies, which opens the chat, or leaves it.
export function CheckinNote({ message, onReply, onLater, onRect }) {
  const measure = useCallback(
    (node) => onRect(node ? node.getBoundingClientRect() : null),
    [onRect],
  );
  return (
    <section
      ref={measure}
      className="checkin-note"
      aria-label="The INVITE Agent is checking in"
      onAnimationEnd={(e) => onRect(e.currentTarget.getBoundingClientRect())}
    >
      <header className="checkin-note__title">
        <MessageCircleMore size={18} strokeWidth={2.4} aria-hidden="true" />
        <h2>Checking in</h2>
        <button type="button" className="checkin-note__close" aria-label="Close" onClick={onLater}>
          <X size={18} aria-hidden="true" />
        </button>
      </header>
      <p className="checkin-note__body" role="status">
        {renderInline(message.body)}
      </p>
      <div className="checkin-note__actions">
        <button type="button" className="gold-button" onClick={onReply}>
          Reply
        </button>
        <button type="button" className="text-button" onClick={onLater}>
          Later
        </button>
      </div>
    </section>
  );
}
