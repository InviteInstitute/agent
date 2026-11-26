import { useEffect, useRef, useState } from "react";
import { Button, IconButton, InlineLoading, Tag, TextArea } from "@carbon/react";
import {
  CheckmarkFilled,
  ChatLaunch,
  Send,
  ThumbsDown,
  ThumbsDownFilled,
  ThumbsUp,
  ThumbsUpFilled,
  WarningFilled,
} from "@carbon/icons-react";

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
                {done ? <CheckmarkFilled size={16} /> : index + 1}
              </span>
              <span>
                {step.text}
                {done ? <span className="cds--visually-hidden"> Done.</span> : null}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="guide__status" role="status">
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
    <InlineLoading
      description={slow ? "Still thinking. This one is taking a moment…" : "Thinking…"}
      className="turn__thinking"
    />
  );
}

// Replies name blocks in `backticks`, and models sometimes bold or italicize a word.
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

  return (
    <div className="rating">
      <div className="rating__row">
        <IconButton
          kind="ghost"
          size="sm"
          label="This helped"
          align="bottom"
          aria-pressed={message.thumb === "up"}
          onClick={() => send("up")}
          disabled={state === "sending"}
        >
          {message.thumb === "up" ? <ThumbsUpFilled /> : <ThumbsUp />}
        </IconButton>
        <IconButton
          kind="ghost"
          size="sm"
          label="This didn't help"
          align="bottom"
          aria-pressed={message.thumb === "down"}
          onClick={() => send("down")}
          disabled={state === "sending"}
        >
          {message.thumb === "down" ? <ThumbsDownFilled /> : <ThumbsDown />}
        </IconButton>
        <Button
          kind="ghost"
          size="sm"
          onClick={() => setNoteOpen((open) => !open)}
          aria-expanded={noteOpen}
        >
          {noteOpen ? "Hide note" : "Add a note"}
        </Button>
        {state && state !== "sending" ? (
          <span className="rating__state" role="status">
            {state}
          </span>
        ) : null}
      </div>
      {noteOpen ? (
        <div className="rating__note">
          <TextArea
            id={`note-${message.id}`}
            labelText="Note about this reply"
            hideLabel
            rows={2}
            maxLength={2000}
            placeholder="What helped, or what was confusing?"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <Button
            size="sm"
            kind="secondary"
            disabled={!note.trim() || !message.thumb || state === "sending"}
            onClick={() => send(message.thumb, note.trim())}
          >
            Send note
          </Button>
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
        <span className="cds--visually-hidden">You said: </span>
        <p className="turn__body">{message.body}</p>
      </article>
    );
  }
  return (
    <article
      className={`turn turn--agent ${message.origin === "proactive" ? "turn--checkin" : ""} ${
        message.failed ? "turn--failed" : ""
      }`}
    >
      {message.origin === "proactive" ? (
        <p className="turn__label">
          <ChatLaunch size={16} aria-hidden="true" />
          Checking in
        </p>
      ) : (
        <span className="cds--visually-hidden">INVITE Agent said: </span>
      )}
      {message.pending ? (
        <Thinking />
      ) : (
        <p className="turn__body">
          {message.failed ? (
            <WarningFilled size={16} className="turn__warning" aria-label="Problem:" />
          ) : null}
          {renderInline(message.body)}
        </p>
      )}
      {message.model ? (
        <div className="turn__research">
          <Tag size="sm" type="purple">
            {message.model}
          </Tag>
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
      <div className="chat" aria-label="Conversation" role="log">
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
          <TextArea
            id="message"
            labelText="Message"
            hideLabel
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
          <IconButton type="submit" label="Send" disabled={busy || !draft.trim()} align="top-end">
            <Send />
          </IconButton>
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
