import { Notice } from "./ui.jsx";

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
        <Notice kind="error" title="Couldn't load the agent settings">
          {error}
        </Notice>
        <button type="button" className="gold-button" onClick={onRetry}>
          Try again
        </button>
      </div>
    );
  }
  if (!config) {
    return (
      <div className="research" aria-busy="true">
        {[90, 70, 95, 60, 85, 40].map((width) => (
          <div key={width} className="skeleton" style={{ width: `${width}%` }} />
        ))}
      </div>
    );
  }

  const update = (patch) => onChange({ ...settings, ...patch });
  const overrides = overridesFor(settings, config);
  const template = settings.promptTemplate ?? config.prompt_template;
  const usage = tokens || config.session_tokens;

  return (
    <div className="research">
      <Notice
        kind={overrides ? "warning" : "info"}
        title={overrides ? "Custom settings are on" : "Production settings"}
      >
        {overrides
          ? "Your replies go to a research chat and stay out of student data."
          : "Replies match what students get."}
      </Notice>
      {usage ? (
        <div className="research__usage">
          <label className="micro" htmlFor="research-usage">
            LLM tokens this session
          </label>
          <progress
            id="research-usage"
            value={Math.min(usage.used, usage.limit)}
            max={usage.limit}
          />
          <p className="field__help">
            {usage.used.toLocaleString()} of {usage.limit.toLocaleString()}
          </p>
        </div>
      ) : null}
      <div className="field">
        <label className="micro" htmlFor="research-model">
          Model
        </label>
        <select
          id="research-model"
          className="select"
          value={settings.model ?? config.defaults.model}
          onChange={(e) => update({ model: e.target.value })}
          aria-invalid={Boolean(config.models_error)}
        >
          {config.models.map((model) => (
            <option key={model} value={model}>
              {model === config.defaults.model ? `${model} (production)` : model}
            </option>
          ))}
        </select>
        {config.models_error ? (
          <p className="field__help composer__notice">{config.models_error}</p>
        ) : null}
      </div>
      <div className="research__row">
        <div className="field">
          <label className="micro" htmlFor="research-temperature">
            Temperature
          </label>
          <input
            id="research-temperature"
            className="input"
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={settings.temperature ?? ""}
            onChange={(e) => update({ temperature: numberOrNull(e.target.value) })}
          />
          <p className="field__help">Empty is the model's default</p>
        </div>
        <div className="field">
          <label className="micro" htmlFor="research-max-tokens">
            Max tokens
          </label>
          <input
            id="research-max-tokens"
            className="input"
            type="number"
            min={16}
            max={4096}
            step={16}
            value={settings.maxTokens ?? ""}
            onChange={(e) => update({ maxTokens: numberOrNull(e.target.value) })}
          />
          <p className="field__help">Empty is {config.defaults.max_tokens}</p>
        </div>
      </div>
      <label className="research__check">
        <input
          type="checkbox"
          checked={settings.trimReply}
          onChange={(e) => update({ trimReply: e.target.checked })}
        />
        Trim replies to bite size, as students get them
      </label>
      <div className="field">
        <label className="micro" htmlFor="research-prompt">
          Prompt template
        </label>
        <textarea
          id="research-prompt"
          className="textarea research__prompt"
          rows={14}
          spellCheck="false"
          value={template}
          onChange={(e) => update({ promptTemplate: e.target.value })}
        />
      </div>
      <details>
        <summary>Placeholders you can use</summary>
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
      </details>
      <button
        type="button"
        className="gold-button"
        disabled={!overrides}
        onClick={() => onChange({ ...PRODUCTION_SETTINGS })}
      >
        Reset to production
      </button>
    </div>
  );
}
