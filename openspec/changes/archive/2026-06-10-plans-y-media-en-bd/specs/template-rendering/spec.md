## ADDED Requirements

### Requirement: Intent response templating with Jinja

The system MUST allow each intent in `kb_intents` to declare a
`response_type` of `static` (default, uses `response_text` as-is),
`template_jinja`, or `data_driven`. When the type is `template_jinja`
or `data_driven`, the system MUST render `response_template` with a
Jinja2 sandboxed environment before sending the bot's reply.

#### Scenario: Static response unchanged
- **WHEN** an intent has `response_type="static"` and `response_text="Hola"`
- **THEN** the system MUST return `"Hola"` as the bot reply with no
  template processing

#### Scenario: Jinja template rendered with plan context
- **WHEN** an intent has `response_template="Planes: {% for p in plans %}{{ p.nombre }} {% endfor %}"`
  and there are two active plans `combo_5` and `solo_vuelo`
- **THEN** the rendered reply MUST be `"Planes: Combo 5 Solo vuelo "`

#### Scenario: Currency filter formats Colombian pesos
- **WHEN** a template contains `{{ plan.precio_cop | currency_cop }}` and
  `plan.precio_cop=290000`
- **THEN** the rendered text MUST contain `"$290.000"`

### Requirement: Safe Jinja sandbox

The template engine MUST be a sandboxed Jinja2 environment that prevents
arbitrary Python execution, attribute access on internal objects, and
loading of external templates.

#### Scenario: Sandbox blocks attribute access on private fields
- **WHEN** a template contains `{{ plan._sa_instance_state }}`
- **THEN** the render MUST raise `SecurityError` and the system MUST fall
  back to `response_text` with a warning log

#### Scenario: Sandbox blocks import
- **WHEN** a template contains `{% import os %}`
- **THEN** the render MUST raise `SecurityError` and MUST NOT execute the
  import

### Requirement: Graceful fallback on render error

If template rendering fails for any reason (syntax error, undefined
variable in strict mode, sandbox violation), the system MUST fall back
to the intent's `response_text` and log a warning with the error and the
intent name. The customer MUST still receive a coherent response.

#### Scenario: Undefined variable falls back
- **WHEN** an intent has `response_template="Hola {{ user.nombre }}"`
  and the variable `user` is not in context
- **THEN** the system MUST send the `response_text` fallback and log a
  warning `"template_render_failed" intent=saludo_puro error=undefined`

#### Scenario: Syntax error caught
- **WHEN** a template has `{% for p in plans %}` without `{% endfor %}`
- **THEN** the system MUST catch `TemplateSyntaxError`, fall back to
  `response_text`, and log the error with the intent name and template
  source

### Requirement: Required context for data-driven intents

When `response_type="data_driven"`, the system MUST require the intent
to declare a non-empty `requires_data` list naming the context keys it
needs. If any of those keys are missing at render time, the system MUST
fall back to `response_text` and log a `template_context_missing`
warning, never crash.

#### Scenario: Missing required data falls back
- **WHEN** an intent has `response_type="data_driven"`,
  `requires_data=["plans", "media"]`, but the `media` context is empty
- **THEN** the system MUST fall back to `response_text` and log
  `"template_context_missing" intent=X missing=media`
