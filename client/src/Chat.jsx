import { useEffect, useRef, useState } from "react";
import { Button, IconButton, InlineLoading, Tag, TextArea } from "@carbon/react";
import { Send, ThumbsDown, ThumbsDownFilled, ThumbsUp, ThumbsUpFilled } from "@carbon/icons-react";

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
      <article className={`turn turn--student ${message.error ? "turn--failed" : ""}`}>
        <span className="cds--visually-hidden">You said: </span>
        <p className="turn__body">{message.body}</p>
        {message.error ? <p className="turn__error">Not sent: {message.error}</p> : null}
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
        <p className="turn__label">Checking in</p>
      ) : (
        <span className="cds--visually-hidden">INVITE Agent said: </span>
      )}
      {message.pending ? (
        <InlineLoading description="Thinking…" className="turn__thinking" />
      ) : (
        <p className="turn__body">{renderInline(message.body)}</p>
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
        {messages.length ? null : (
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
