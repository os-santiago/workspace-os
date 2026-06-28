# Model Providers

Workspace OS can run without an external model. That is the default.

When you want a stronger planning or review brain, enable the optional model provider layer through the workspace config or matching environment variables.

## Default behavior

- If `modeling.enabled` is `false` or absent, WOS uses the no-model fallback.
- The no-model provider keeps the cycle and routing flow working.
- Agent orchestration remains independent from the model choice.

## Config example

```json
{
  "modeling": {
    "enabled": true,
    "default_profile": "remote_reasoner",
    "fallback_profile": "none",
    "routes": {
      "planning": ["remote_reasoner"],
      "review": ["remote_reasoner"]
    },
    "profiles": {
      "remote_reasoner": {
        "kind": "openai_compatible",
        "enabled": true,
        "base_url_env": "WOS_MODEL_BASE_URL",
        "api_key_env": "WOS_MODEL_API_KEY",
        "model_env": "WOS_MODEL_NAME"
      }
    }
  }
}
```

## Environment variables

- `WOS_MODELING_ENABLED`
- `WOS_MODEL_DEFAULT_PROFILE`
- `WOS_MODEL_FALLBACK_PROFILE`
- `WOS_MODEL_BASE_URL`
- `WOS_MODEL_API_KEY`
- `WOS_MODEL_NAME`
- `WOS_MODEL_PROFILE_NAME`
- `WOS_MODEL_KIND`

## Notes

- Use an OpenAI-compatible local server or remote API when you want WOS to reason with a stronger model.
- Leave the section disabled if you want the repo to stay fully functional with no external model access.
- The chosen provider is printed in workflow logs so cycles can show which brain path was used.
