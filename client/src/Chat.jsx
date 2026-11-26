import { useEffect, useRef, useState } from "react";
import {
  Check,
  MessageCircleMore,
  SendHorizontal,
  ThumbsDown,
  ThumbsUp,
  TriangleAlert,
} from "lucide-react";
import { Spinner } from "./ui.jsx";

// A reply usually takes a second or two. Past this the student is told it is still coming.
export const SLOW_REPLY_MS = 6000;

// The first-run walkthrough: what a student does before the agent can help, per environment.
// A step is done once the agent can see their code.
export function guideSteps({ environment, studentId }) {
  const ask = { key: "ask", text: "Ask me a question here, or press Help." };
  if (environment === "vexcode-vr") {
    return [
      {
        key: "login",
        text: (
          <>
            In VEXcode VR, log in with your class code and the same Student ID,{" "}
            <strong>{studentId}</strong>.
          </>
        ),
        needsCode: true,
      },
      { key: "run", text: "Run your program once, so I can see your code.", needsCode: true },
      ask,
    ];
  }
  return [
    {
      key: "run",
      text: "Build a program and run it once, so I can see your code.",
      needsCode: true,
    },
    ask,
  ];
}

function Guide({ guide }) {
  return (
    <section className="guide" aria-label="Getting started">
      <h2 className="guide__title">Hi! I'm your coding helper.</h2>
      <ol className="guide__steps">
        {guideSteps(guide).map((step, index) => {
          const done = step.needsCode && guide.seesCode;
          return (
            <li key={step.key} className={done ? "guide__step guide__step--done" : "guide__step"}>
              <span className="guide__marker" aria-hidden="true">
                {done ? <Check size={15} strokeWidth={3} /> : index + 1}
              </span>
              <span>
                {step.text}
                {done ? <span className="visually-hidden"> Done.</span> : null}
              </span>
            </li>
          );
        })}
      </ol>
      <p
        className={guide.seesCode ? "guide__status guide__status--seen" : "guide__status"}
        role="status"
      >
        {guide.seesCode
          ? `I can see your code${guide.playground ? ` in ${guide.playground}` : ""}!`
          : "I can't see your code yet."}
      </p>
    </section>
  );
}

// "Thinking", then a word of reassurance if the reply is slow.
function Thinking() {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), SLOW_REPLY_MS);
    return () => clearTimeout(timer);
  }, []);
  return (
    <Spinner
      className="thinking"
      label={slow ? "Still thinking. This one is taking a moment…" : "Thinking…"}
    />
  );
}

// Replies name blocks in `backticks`, and models sometimes bold or italicize a word. A block
// name shows as a small VEX block.
export function renderInline(text) {
  const parts = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const token = match[0];
    const key = match.index;
    if (token.startsWith("**")) parts.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    else if (token.startsWith("`"))
      parts.push(
        <code key={key} className="block-name">
          {token.slice(1, -1)}
        </code>,
      );
    else parts.push(<em key={key}>{token.slice(1, -1)}</em>);
    last = match.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function Rating({ message, onRate }) {
  const [noteOpen, setNoteOpen] = useState(false);
  const [note, setNote] = useState("");
  const [state, setState] = useState("");

  const send = async (thumb, comment) => {
    setState("sending");
    try {
      await onRate(message, thumb, comment);
      setState(comment ? "Note sent." : "Thanks!");
      if (comment) setNoteOpen(false);
    } catch (error) {
      setState(`Not sent: ${error.message}`);
    }
  };

  const thumb = (value, label, Icon) => (
    <button
      type="button"
      className="thumb"
      aria-label={label}
      title={label}
      aria-pressed={message.thumb === value}
      onClick={() => send(value)}
      disabled={state === "sending"}
    >
      <Icon size={17} />
    </button>
  );

  return (
    <div className="rating">
      <div className="rating__row">
        {thumb("up", "This helped", ThumbsUp)}
        {thumb("down", "This didn't help", ThumbsDown)}
        <button
          type="button"
          className="text-button"
          onClick={() => setNoteOpen((open) => !open)}
          aria-expanded={noteOpen}
        >
          {noteOpen ? "Hide note" : "Add a note"}
        </button>
        {state && state !== "sending" ? (
          <span className="rating__state" role="status">
            {state}
          </span>
        ) : null}
      </div>
      {noteOpen ? (
        <div className="rating__note">
          <label className="visually-hidden" htmlFor={`note-${message.id}`}>
            Note about this reply
          </label>
          <textarea
            id={`note-${message.id}`}
            className="textarea"
            rows={2}
            maxLength={2000}
            placeholder="What helped, or what was confusing?"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <button
            type="button"
            className="gold-button"
            disabled={!note.trim() || !message.thumb || state === "sending"}
            onClick={() => send(message.thumb, note.trim())}
          >
            Send note
          </button>
          {!message.thumb ? <p className="rating__hint">Pick thumbs up or down first.</p> : null}
        </div>
      ) : null}
    </div>
  );
}

function Turn({ message, onRate }) {
  if (message.role === "student") {
    return (
      <article className="turn turn--student">
        <span className="visually-hidden">You said: </span>
        <p className="turn__body">{message.body}</p>
      </article>
    );
  }
  const classes = ["turn", "turn--agent"];
  if (message.origin === "proactive") classes.push("turn--checkin");
  if (message.failed) classes.push("turn--failed");
  return (
    <article className={classes.join(" ")}>
      {message.origin === "proactive" ? (
        <p className="turn__label">
          <MessageCircleMore size={14} strokeWidth={2.4} aria-hidden="true" />
          Checking in
        </p>
      ) : (
        <span className="visually-hidden">INVITE Agent said: </span>
      )}
      {message.pending ? (
        <Thinking />
      ) : (
        <p className="turn__body">
          {message.failed ? (
            <TriangleAlert size={16} className="turn__warning" aria-label="Problem:" />
          ) : null}
          {renderInline(message.body)}
        </p>
      )}
      {message.model ? (
        <div className="turn__research">
          <span className="pill">{message.model}</span>
          {message.tokens ? <span>{message.tokens.toLocaleString()} tokens</span> : null}
          {message.prompt ? (
            <details>
              <summary>Prompt</summary>
              <pre>{message.prompt}</pre>
            </details>
          ) : null}
        </div>
      ) : null}
      {message.responseId && !message.pending ? <Rating message={message} onRate={onRate} /> : null}
    </article>
  );
}

export default function Chat({
  messages,
  onSend,
  onRate,
  busy,
  customNote,
  notice,
  composerExtra,
  guide,
}) {
  const [draft, setDraft] = useState("");
  const end = useRef(null);

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages]);

  const send = (event) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    onSend(text);
  };

  return (
    <>
      <div className="chat dotted" aria-label="Conversation" role="log">
        {messages.length ? null : guide ? (
          <Guide guide={guide} />
        ) : (
          <p className="chat__empty">
            Ask me about your project, or press Help and I'll look at your code.
          </p>
        )}
        {messages.map((message) => (
          <Turn key={message.id} message={message} onRate={onRate} />
        ))}
        <div ref={end} />
      </div>
      <form className="composer" onSubmit={send}>
        {customNote ? <p className="composer__custom">{customNote}</p> : null}
        <div className="composer__row">
          <label className="visually-hidden" htmlFor="message">
            Message
          </label>
          <textarea
            id="message"
            className="textarea"
            rows={2}
            maxLength={2000}
            placeholder="Ask about your program, your bug, or what to try next."
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) send(e);
            }}
          />
          {composerExtra}
          <button
            type="submit"
            className="gold-button gold-button--square"
            aria-label="Send"
            title="Send"
            disabled={busy || !draft.trim()}
          >
            <SendHorizontal size={20} strokeWidth={2.4} />
          </button>
        </div>
        {notice ? (
          <p className="composer__notice" role="alert">
            {notice}
          </p>
        ) : null}
      </form>
    </>
  );
}
