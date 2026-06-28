from __future__ import annotations

from dataclasses import dataclass, field, replace
import http.client
import json
import os
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlparse


@dataclass(frozen=True)
class ModelMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ModelRequest:
    task_type: str = "general"
    messages: tuple[ModelMessage, ...] = ()
    temperature: float = 0.2
    top_p: float = 0.95
    max_tokens: int | None = None
    reasoning_budget: int | None = None
    extra_body: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_prompt(
        cls,
        prompt: str,
        task_type: str = "general",
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> "ModelRequest":
        messages: list[ModelMessage] = []
        if system_prompt:
            messages.append(ModelMessage(role="system", content=system_prompt))
        messages.append(ModelMessage(role="user", content=prompt))
        return cls(task_type=task_type, messages=tuple(messages), **kwargs)

    def prompt_text(self) -> str:
        return "\n".join(f"{message.role}: {message.content}" for message in self.messages).strip()


@dataclass(frozen=True)
class ModelResult:
    provider: str
    model: str | None
    content: str
    used_fallback: bool
    candidate_chain: tuple[str, ...] = ()
    fallback_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def render_summary(self) -> str:
        fallback = " fallback" if self.used_fallback else ""
        model = self.model or "n/a"
        reason = f" reason={self.fallback_reason}" if self.fallback_reason else ""
        return f"provider={self.provider} model={model}{fallback}{reason}"


class ModelProviderError(RuntimeError):
    pass


@runtime_checkable
class ModelProvider(Protocol):
    name: str

    def is_available(self) -> bool:
        ...

    def generate(self, request: ModelRequest) -> ModelResult:
        ...


@dataclass(frozen=True)
class ModelProfile:
    name: str
    kind: str = "none"
    enabled: bool = True
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    base_url_env: str | None = None
    api_key_env: str | None = None
    model_env: str | None = None


@dataclass(frozen=True)
class ModelRoutingConfig:
    enabled: bool = False
    default_profile: str = "none"
    fallback_profile: str = "none"
    routes: dict[str, tuple[str, ...]] = field(default_factory=dict)
    profiles: dict[str, ModelProfile] = field(default_factory=dict)


class NoModelProvider:
    name = "none"

    def is_available(self) -> bool:
        return True

    def generate(self, request: ModelRequest) -> ModelResult:
        excerpt = request.prompt_text()
        if len(excerpt) > 400:
            excerpt = excerpt[:397] + "..."
        content = "\n".join(
            [
                "No external model configured.",
                f"task_type={request.task_type}",
                "fallback_mode=rule_based",
                excerpt or "request=empty",
            ]
        )
        return ModelResult(
            provider=self.name,
            model=None,
            content=content,
            used_fallback=True,
            fallback_reason="no external model configured",
            metadata={"mode": "no_model"},
        )


class OpenAICompatibleProvider:
    def __init__(
        self,
        name: str,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.base_url = _normalize_http_base_url(base_url)
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.extra_headers = extra_headers or {}

    def is_available(self) -> bool:
        return bool(self.base_url and self.model)

    def generate(self, request_payload: ModelRequest) -> ModelResult:
        if not self.is_available():
            raise ModelProviderError(f"Provider '{self.name}' is not configured.")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [message.__dict__ for message in request_payload.messages],
            "temperature": request_payload.temperature,
            "top_p": request_payload.top_p,
            "stream": False,
        }
        if request_payload.max_tokens is not None:
            payload["max_tokens"] = request_payload.max_tokens
        if request_payload.reasoning_budget is not None:
            payload["reasoning_budget"] = request_payload.reasoning_budget
        if request_payload.extra_body:
            payload.update(request_payload.extra_body)

        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ModelProviderError(f"Provider '{self.name}' has an invalid base URL.")
        endpoint_path = parsed.path.rstrip("/") + "/chat/completions"
        if not endpoint_path.startswith("/"):
            endpoint_path = f"/{endpoint_path}"
        if parsed.query:
            endpoint_path = f"{endpoint_path}?{parsed.query}"
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = json.dumps(payload).encode("utf-8")
        connection_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        connection = connection_cls(parsed.netloc, timeout=self.timeout_seconds)

        try:
            connection.request("POST", endpoint_path, body=body, headers=headers)
            response = connection.getresponse()
            response_body = response.read().decode("utf-8")
            if not 200 <= int(getattr(response, "status", 200)) < 300:
                raise ModelProviderError(f"Provider '{self.name}' returned HTTP {getattr(response, 'status', 'n/a')}.")
            data = json.loads(response_body)
        except http.client.HTTPException as exc:
            raise ModelProviderError(f"Provider '{self.name}' failed: {exc}.") from exc
        except TimeoutError as exc:
            raise ModelProviderError(f"Provider '{self.name}' timed out.") from exc
        except json.JSONDecodeError as exc:
            raise ModelProviderError(f"Provider '{self.name}' returned invalid JSON.") from exc
        finally:
            try:
                connection.close()
            except OSError:
                pass

        choices = data.get("choices", [])
        if not choices:
            raise ModelProviderError(f"Provider '{self.name}' returned no choices.")

        message = choices[0].get("message", {})
        content = message.get("content")
        if not isinstance(content, str):
            raise ModelProviderError(f"Provider '{self.name}' did not return message content.")

        return ModelResult(
            provider=self.name,
            model=self.model,
            content=content,
            used_fallback=False,
            metadata={"raw_response": data},
        )


class ModelRouter:
    def __init__(
        self,
        config: ModelRoutingConfig,
        providers: dict[str, ModelProvider] | None = None,
    ) -> None:
        self.config = config
        self.providers = providers or {}
        self.providers.setdefault("none", NoModelProvider())

    def candidate_chain(self, task_type: str, preferred_profile: str | None = None) -> tuple[str, ...]:
        if not self.config.enabled:
            return ("none",)
        candidates: list[str] = []
        if preferred_profile:
            candidates.append(preferred_profile)
        candidates.extend(self.config.routes.get(task_type, ()))
        candidates.append(self.config.default_profile)
        candidates.append(self.config.fallback_profile)
        candidates.append("none")
        return _dedupe(candidates)

    def select_provider(self, task_type: str, preferred_profile: str | None = None) -> ModelProvider:
        for name in self.candidate_chain(task_type, preferred_profile):
            provider = self.providers.get(name)
            if provider and provider.is_available():
                return provider
        return self.providers["none"]

    def generate(self, request_payload: ModelRequest, preferred_profile: str | None = None) -> ModelResult:
        chain = self.candidate_chain(request_payload.task_type, preferred_profile)
        last_error: str | None = None

        for index, profile_name in enumerate(chain):
            provider = self.providers.get(profile_name)
            if provider is None or not provider.is_available():
                continue
            try:
                result = provider.generate(request_payload)
            except ModelProviderError as exc:
                last_error = str(exc)
                continue

            used_fallback = index > 0 or result.used_fallback
            if result.provider == provider.name and result.candidate_chain == chain and result.used_fallback == used_fallback:
                return result
            return replace(
                result,
                used_fallback=used_fallback,
                candidate_chain=chain,
                fallback_reason=result.fallback_reason or last_error,
                metadata={
                    **result.metadata,
                    "candidate_chain": chain,
                    "selected_profile": profile_name,
                    "fallback_reason": result.fallback_reason or last_error,
                },
            )

        fallback = self.providers["none"].generate(request_payload)
        if last_error:
            return replace(
                fallback,
                candidate_chain=chain,
                fallback_reason=last_error,
                metadata={**fallback.metadata, "candidate_chain": chain, "fallback_reason": last_error},
            )
        return replace(fallback, candidate_chain=chain, metadata={**fallback.metadata, "candidate_chain": chain})


def load_modeling_config(config_path: Path | None) -> ModelRoutingConfig:
    payload: dict[str, Any] = {}
    if config_path and config_path.exists():
        with config_path.expanduser().resolve().open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if not isinstance(loaded, dict):
            raise ValueError("Workspace config must be a JSON object.")
        payload = loaded

    raw_modeling = payload.get("modeling", {})
    if raw_modeling is None:
        raw_modeling = {}
    if not isinstance(raw_modeling, dict):
        raise ValueError("Workspace config 'modeling' section must be an object when present.")

    enabled = _read_bool("WOS_MODELING_ENABLED", bool(raw_modeling.get("enabled", False)))
    default_profile = _read_str("WOS_MODEL_DEFAULT_PROFILE", raw_modeling.get("default_profile", "none")) or "none"
    fallback_profile = _read_str("WOS_MODEL_FALLBACK_PROFILE", raw_modeling.get("fallback_profile", "none")) or "none"

    profiles: dict[str, ModelProfile] = {
        "none": ModelProfile(name="none", kind="none", enabled=True),
    }

    raw_profiles = raw_modeling.get("profiles", {})
    if raw_profiles and not isinstance(raw_profiles, dict):
        raise ValueError("Workspace config 'modeling.profiles' must be an object when present.")

    for name, raw_profile in (raw_profiles or {}).items():
        profiles[name] = _parse_profile(name, raw_profile)

    env_profile = _build_environment_profile()
    if env_profile is not None:
        profiles[env_profile.name] = env_profile

    routes = _parse_routes(raw_modeling.get("routes", {}))
    return ModelRoutingConfig(
        enabled=enabled,
        default_profile=default_profile,
        fallback_profile=fallback_profile,
        routes=routes,
        profiles=profiles,
    )


def build_model_router(config_path: Path | None = None) -> ModelRouter:
    config = load_modeling_config(config_path)
    providers: dict[str, ModelProvider] = {"none": NoModelProvider()}

    if config.enabled:
        for profile in config.profiles.values():
            provider = _build_provider(profile)
            if provider is not None and provider.is_available():
                providers[profile.name] = provider

    return ModelRouter(config, providers)


def _build_provider(profile: ModelProfile) -> ModelProvider | None:
    if not profile.enabled:
        return None

    if profile.kind == "none":
        return NoModelProvider()

    if profile.kind in {"openai_compatible", "openai-compatible"}:
        base_url = _resolve_setting(profile.base_url, profile.base_url_env)
        model = _resolve_setting(profile.model, profile.model_env)
        api_key = _resolve_setting(profile.api_key, profile.api_key_env)
        if not base_url or not model:
            return None
        try:
            return OpenAICompatibleProvider(profile.name, base_url, model, api_key=api_key)
        except ModelProviderError:
            return None

    raise ValueError(f"Unsupported model profile kind '{profile.kind}' for profile '{profile.name}'.")


def _parse_profile(name: str, raw_profile: Any) -> ModelProfile:
    if not isinstance(raw_profile, dict):
        raise ValueError(f"Model profile '{name}' must be an object.")

    kind = _read_str(None, raw_profile.get("kind", "none")) or "none"
    enabled = bool(raw_profile.get("enabled", True))
    return ModelProfile(
        name=name,
        kind=kind,
        enabled=enabled,
        model=_resolve_setting(_read_optional_str(raw_profile.get("model")), _read_optional_str(raw_profile.get("model_env"))),
        base_url=_resolve_setting(_read_optional_str(raw_profile.get("base_url")), _read_optional_str(raw_profile.get("base_url_env"))),
        api_key=_resolve_setting(_read_optional_str(raw_profile.get("api_key")), _read_optional_str(raw_profile.get("api_key_env"))),
        base_url_env=_read_optional_str(raw_profile.get("base_url_env")),
        api_key_env=_read_optional_str(raw_profile.get("api_key_env")),
        model_env=_read_optional_str(raw_profile.get("model_env")),
    )


def _build_environment_profile() -> ModelProfile | None:
    base_url = _read_str("WOS_MODEL_BASE_URL", "")
    model = _read_str("WOS_MODEL_NAME", "")
    api_key = _read_str("WOS_MODEL_API_KEY", "")
    if not base_url or not model:
        return None
    return ModelProfile(
        name=_read_str("WOS_MODEL_PROFILE_NAME", "environment") or "environment",
        kind=_read_str("WOS_MODEL_KIND", "openai_compatible") or "openai_compatible",
        enabled=True,
        base_url=base_url,
        model=model,
        api_key=api_key or None,
    )


def _parse_routes(raw_routes: Any) -> dict[str, tuple[str, ...]]:
    if raw_routes in (None, {}):
        return {}
    if not isinstance(raw_routes, dict):
        raise ValueError("Workspace config 'modeling.routes' must be an object when present.")

    routes: dict[str, tuple[str, ...]] = {}
    for task_type, raw_targets in raw_routes.items():
        if not isinstance(task_type, str) or not task_type.strip():
            raise ValueError("Model routing task keys must be non-empty strings.")
        if isinstance(raw_targets, str):
            targets = (raw_targets.strip(),)
        elif isinstance(raw_targets, list):
            targets = tuple(target.strip() for target in raw_targets if isinstance(target, str) and target.strip())
        else:
            raise ValueError(f"Routing targets for '{task_type}' must be a string or list of strings.")
        routes[task_type.strip()] = targets
    return routes


def _resolve_setting(value: str | None, env_name: str | None) -> str | None:
    if env_name:
        env_value = os.environ.get(env_name, "").strip()
        if env_value:
            return env_value
    return value.strip() if isinstance(value, str) and value.strip() else None


def _read_str(env_name: str | None, default: str | None) -> str | None:
    if env_name:
        env_value = os.environ.get(env_name, "").strip()
        if env_value:
            return env_value
    if isinstance(default, str) and default.strip():
        return default.strip()
    return None


def _read_bool(env_name: str, default: bool) -> bool:
    raw = os.environ.get(env_name, "").strip().casefold()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _read_optional_str(raw: Any) -> str | None:
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _normalize_http_base_url(base_url: str) -> str:
    parsed = urlparse(base_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ModelProviderError("Model provider base_url must use http or https.")
    if not parsed.netloc:
        raise ModelProviderError("Model provider base_url must include a host.")
    if parsed.query or parsed.fragment:
        raise ModelProviderError("Model provider base_url must not include query or fragment parts.")
    return base_url.strip().rstrip("/")


def _dedupe(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)
