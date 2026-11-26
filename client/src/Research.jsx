import {
  Accordion,
  AccordionItem,
  Button,
  Checkbox,
  InlineNotification,
  NumberInput,
  ProgressBar,
  Select,
  SelectItem,
  SkeletonText,
  TextArea,
} from "@carbon/react";

// The research page: a model, the prompt template and sampling for this browser's replies. The
// settings ride on each turn as overrides, which sends it to the research chat, kept apart from
// what students see. Nothing here changes what the production agent says.

export const PRODUCTION_SETTINGS = {
  model: null,
  promptTemplate: null,
  temperature: null,
  maxTokens: null,
  trimReply: true,
};

// The overrides for /turns, or null when every setting matches production.
export function overridesFor(settings, config) {
  if (!config?.defaults) return null;
  const overrides = {};
  if (settings.model && settings.model !== config.defaults.model) overrides.model = settings.model;
  if (settings.promptTemplate !== null && settings.promptTemplate !== config.prompt_template)
    overrides.prompt_template = settings.promptTemplate;
  if (settings.temperature !== null) overrides.temperature = settings.temperature;
  if (settings.maxTokens !== null) overrides.max_tokens = settings.maxTokens;
  if (!settings.trimReply) overrides.trim_reply = false;
  return Object.keys(overrides).length ? overrides : null;
}

export function describeOverrides(overrides) {
  if (!overrides) return "";
  const parts = [];
  if (overrides.model) parts.push(overrides.model);
  if (overrides.prompt_template) parts.push("edited prompt");
  if (overrides.temperature !== undefined) parts.push(`temperature ${overrides.temperature}`);
  if (overrides.max_tokens !== undefined) parts.push(`${overrides.max_tokens} max tokens`);
  if (overrides.trim_reply === false) parts.push("no trim");
  return parts.join(", ");
}

const numberOrNull = (value) =>
  value === "" || value === null || Number.isNaN(Number(value)) ? null : Number(value);

export default function Research({ config, error, onRetry, settings, onChange, tokens }) {
  if (error) {
    return (
      <div className="research">
        <InlineNotification
          kind="error"
          title="Couldn't load the agent settings"
          subtitle={error}
          lowContrast
          hideCloseButton
        />
        <Button kind="tertiary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }
  if (!config) {
    return (
      <div className="research" aria-busy="true">
        <SkeletonText paragraph lineCount={6} />
      </div>
    );
  }

  const update = (patch) => onChange({ ...settings, ...patch });
  const overrides = overridesFor(settings, config);
  const template = settings.promptTemplate ?? config.prompt_template;
  const usage = tokens || config.session_tokens;

  return (
    <div className="research">
      <InlineNotification
        kind={overrides ? "warning" : "info"}
        title={overrides ? "Custom settings are on" : "Production settings"}
        subtitle={
          overrides
            ? "Your replies go to a research chat and stay out of student data."
            : "Replies match what students get."
        }
        lowContrast
        hideCloseButton
      />
      {usage ? (
        <ProgressBar
          label="LLM tokens this session"
          helperText={`${usage.used.toLocaleString()} of ${usage.limit.toLocaleString()}`}
          value={Math.min(usage.used, usage.limit)}
          max={usage.limit}
          status={usage.used >= usage.limit ? "error" : "active"}
          size="small"
        />
      ) : null}
      <Select
        id="research-model"
        labelText="Model"
        value={settings.model ?? config.defaults.model}
        onChange={(e) => update({ model: e.target.value })}
        invalid={Boolean(config.models_error)}
        invalidText={config.models_error}
      >
        {config.models.map((model) => (
          <SelectItem
            key={model}
            value={model}
            text={model === config.defaults.model ? `${model} (production)` : model}
          />
        ))}
      </Select>
      <div className="research__row">
        <NumberInput
          id="research-temperature"
          label="Temperature"
          helperText="Empty is the model's default"
          min={0}
          max={2}
          step={0.1}
          allowEmpty
          value={settings.temperature ?? ""}
          onChange={(_, { value }) => update({ temperature: numberOrNull(value) })}
        />
        <NumberInput
          id="research-max-tokens"
          label="Max tokens"
          helperText={`Empty is ${config.defaults.max_tokens}`}
          min={16}
          max={4096}
          step={16}
          allowEmpty
          value={settings.maxTokens ?? ""}
          onChange={(_, { value }) => update({ maxTokens: numberOrNull(value) })}
        />
      </div>
      <Checkbox
        id="research-trim"
        labelText="Trim replies to bite size, as students get them"
        checked={settings.trimReply}
        onChange={(_, { checked }) => update({ trimReply: checked })}
      />
      <TextArea
        id="research-prompt"
        className="research__prompt"
        labelText="Prompt template"
        rows={14}
        spellCheck="false"
        value={template}
        onChange={(e) => update({ promptTemplate: e.target.value })}
      />
      <Accordion size="sm">
        <AccordionItem title="Placeholders you can use">
          <dl className="research__placeholders">
            {Object.entries(config.placeholders).map(([name, description]) => (
              <div key={name}>
                <dt>
                  <code>{`{${name}}`}</code>
                </dt>
                <dd>{description}</dd>
              </div>
            ))}
          </dl>
        </AccordionItem>
      </Accordion>
      <Button
        kind="tertiary"
        size="sm"
        disabled={!overrides}
        onClick={() => onChange({ ...PRODUCTION_SETTINGS })}
      >
        Reset to production
      </Button>
    </div>
  );
}
