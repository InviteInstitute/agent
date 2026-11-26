import { useState } from "react";
import {
  Button,
  Form,
  InlineNotification,
  RadioButton,
  RadioButtonGroup,
  TextInput,
} from "@carbon/react";
import { ArrowRight } from "@carbon/icons-react";

// The start card. A teacher's link can fill it in: ?env=zany&class=room-4&student=S01.
export function linkedStudent(search = window.location.search) {
  const query = new URLSearchParams(search);
  return {
    environment: query.get("env") || "",
    studentId: query.get("student") || "",
    classCode: query.get("class") || "",
  };
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
    <Form className="sign-in" onSubmit={submit} aria-label="Sign in">
      <p className="sign-in__lead">
        Hi! I'm your coding helper. Sign in with what your teacher gave you.
      </p>
      {environments.length > 1 ? (
        <RadioButtonGroup
          legendText="Where are you coding?"
          name="environment"
          valueSelected={environment}
          onChange={setEnvironment}
          orientation="horizontal"
        >
          {environments.map((e) => (
            <RadioButton key={e.id} id={`environment-${e.id}`} labelText={e.name} value={e.id} />
          ))}
        </RadioButtonGroup>
      ) : null}
      {chosen.needs_class_code ? (
        <TextInput
          id="class-code"
          labelText="Class code"
          value={classCode}
          onChange={(e) => setClassCode(e.target.value)}
          autoComplete="off"
          spellCheck="false"
          maxLength={100}
          disabled={pending}
        />
      ) : null}
      <TextInput
        id="student-id"
        labelText="Student ID"
        placeholder="e.g. mars-042"
        value={studentId}
        onChange={(e) => setStudentId(e.target.value)}
        autoComplete="off"
        spellCheck="false"
        maxLength={100}
        disabled={pending}
      />
      {error ? (
        <InlineNotification
          kind="error"
          title="Couldn't start"
          subtitle={error}
          lowContrast
          hideCloseButton
        />
      ) : null}
      <Button type="submit" renderIcon={ArrowRight} disabled={!ready || pending}>
        {pending ? "Starting…" : "Start chat"}
      </Button>
    </Form>
  );
}
