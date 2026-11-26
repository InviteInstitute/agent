import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { Notice } from "./ui.jsx";

// The start card. A teacher's link can fill it in: ?env=zany&class=room-4&student=S01.
export function linkedStudent(search = window.location.search) {
  const query = new URLSearchParams(search);
  return {
    environment: query.get("env") || "",
    studentId: query.get("student") || "",
    classCode: query.get("class") || "",
  };
}

function Field({ id, label, ...input }) {
  return (
    <div className="field">
      <label className="micro" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className="input"
        autoComplete="off"
        spellCheck="false"
        maxLength={100}
        {...input}
      />
    </div>
  );
}

export default function SignIn({ environments, onSignIn, pending, error }) {
  const linked = linkedStudent();
  const [environment, setEnvironment] = useState(
    environments.some((e) => e.id === linked.environment) ? linked.environment : environments[0].id,
  );
  const [studentId, setStudentId] = useState(linked.studentId);
  const [classCode, setClassCode] = useState(linked.classCode);
  const chosen = environments.find((e) => e.id === environment);
  const ready = studentId.trim() && (!chosen.needs_class_code || classCode.trim());

  const submit = (event) => {
    event.preventDefault();
    if (!ready || pending) return;
    onSignIn({
      environment,
      studentId: studentId.trim(),
      classCode: chosen.needs_class_code ? classCode.trim() : "",
    });
  };

  return (
    <form className="sign-in" onSubmit={submit} aria-label="Sign in">
      <p className="sign-in__lead">
        Hi! I'm your coding helper. Sign in with what your teacher gave you.
      </p>
      {environments.length > 1 ? (
        <div role="group" aria-labelledby="environment-label">
          <span className="micro" id="environment-label">
            Where are you coding?
          </span>
          <div className="halves">
            {environments.map((e) => (
              <button
                key={e.id}
                type="button"
                aria-pressed={e.id === environment}
                onClick={() => setEnvironment(e.id)}
                disabled={pending}
              >
                {e.name}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {chosen.needs_class_code ? (
        <Field
          id="class-code"
          label="Class code"
          value={classCode}
          onChange={(e) => setClassCode(e.target.value)}
          disabled={pending}
        />
      ) : null}
      <Field
        id="student-id"
        label="Student ID"
        placeholder="e.g. mars-042"
        value={studentId}
        onChange={(e) => setStudentId(e.target.value)}
        disabled={pending}
      />
      {error ? (
        <Notice kind="error" title="Couldn't start">
          {error}
        </Notice>
      ) : null}
      <button type="submit" className="gold-button gold-button--wide" disabled={!ready || pending}>
        {pending ? "Starting…" : "Start chat"}
        <ArrowRight size={18} strokeWidth={2.4} aria-hidden="true" />
      </button>
    </form>
  );
}
