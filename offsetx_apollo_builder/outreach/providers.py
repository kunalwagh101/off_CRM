from __future__ import annotations

import ipaddress
import json
import os
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from .models import AIProvider, ProviderConfig


class ProviderError(RuntimeError):
    pass


class ProviderUnavailableError(ProviderError):
    """Raised when every configured provider is unavailable or invalid."""


#: Legacy draft-generation path policies.
#:
#: ``strict`` behaves exactly like this path's ``minimal`` — recipient identity
#: removed entirely.  Note the difference from the AI module: there,
#: ``minimal`` deliberately permits the person's public name so enrichment can
#: personalise, and ``strict`` is the level that removes it.  The two paths keep
#: their own meanings so existing profiles do not silently start sending more.
#: New work should go through ``offsetx_apollo_builder.ai.broker.EgressBroker``.
DATA_POLICIES = {"strict", "minimal", "standard", "full"}


def _redact_text(value: str) -> str:
    value = re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "[redacted-email]",
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(r"https?://\S+", "[redacted-url]", value)


def apply_data_policy(user_prompt: str, policy: str) -> str:
    """Minimize provider payloads while retaining the canonical generation contract."""
    if policy not in DATA_POLICIES:
        raise ProviderError(f"Unsupported provider data policy: {policy}")
    if policy == "full":
        return user_prompt
    try:
        payload = json.loads(user_prompt)
    except json.JSONDecodeError:
        return _redact_text(user_prompt)
    if not isinstance(payload, dict):
        return _redact_text(user_prompt)
    recipient = payload.get("recipient") if isinstance(payload.get("recipient"), dict) else {}
    if policy in {"minimal", "strict"}:
        private_values = [
            str(recipient.get(key, ""))
            for key in ("first_name", "full_name", "company", "title", "public_hook", "hook_source")
            if recipient.get(key)
        ]
        payload["recipient"] = {
            key: recipient[key]
            for key in ("category", "route", "tension", "contribution", "question_1", "question_2", "question_3")
            if recipient.get(key)
        }
        serialized = json.dumps(payload, ensure_ascii=False)
        for value in sorted(private_values, key=len, reverse=True):
            serialized = re.sub(re.escape(value), "[redacted-recipient]", serialized, flags=re.IGNORECASE)
        return _redact_text(serialized)
    for key in ("email", "linkedin_url", "hook_source", "source_ref"):
        recipient.pop(key, None)
    payload["recipient"] = recipient
    return _redact_text(json.dumps(payload, ensure_ascii=False))


class PolicyAIProvider:
    """Provider wrapper enforcing data minimization and a redacted call audit."""

    def __init__(
        self,
        provider: AIProvider,
        *,
        profile_id: str,
        provider_type: str,
        model: str,
        data_policy: str = "minimal",
        audit_payloads: bool = False,
        audit_callback: Any | None = None,
    ) -> None:
        if data_policy not in DATA_POLICIES:
            raise ProviderError(f"Unsupported provider data policy: {data_policy}")
        self.provider = provider
        self.profile_id = profile_id
        self.provider_type = provider_type
        self.model = model
        self.data_policy = data_policy
        self.audit_payloads = audit_payloads
        self.audit_callback = audit_callback
        self.last_run: dict[str, Any] = {}

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        minimized = apply_data_policy(user_prompt, self.data_policy)
        started = time.monotonic()
        status = "succeeded"
        output = ""
        error = ""
        try:
            output = self.provider.generate(system_prompt=system_prompt, user_prompt=minimized)
            return output
        except Exception as exc:
            status = "failed"
            error = str(exc)
            raise
        finally:
            duration_ms = int((time.monotonic() - started) * 1000)
            request_payload = (
                {"system_prompt": system_prompt[:12000], "user_prompt": minimized[:30000]}
                if self.audit_payloads
                else {"payload_logging": "disabled", "user_prompt_chars": len(minimized)}
            )
            response_payload = (
                {"text": output[:30000]}
                if self.audit_payloads and output
                else {"payload_logging": "disabled", "response_chars": len(output)}
            )
            if self.audit_callback:
                try:
                    self.audit_callback(
                        profile_id=self.profile_id,
                        provider_type=self.provider_type,
                        model=self.model,
                        data_policy=self.data_policy,
                        status=status,
                        request_payload=request_payload,
                        response_payload=response_payload,
                        error=error,
                        duration_ms=duration_ms,
                    )
                except Exception:
                    pass
            self.last_run = {
                "selected_profile_id": self.profile_id if status == "succeeded" else "",
                "attempts": [{"profile_id": self.profile_id, "status": status, "duration_ms": duration_ms}],
            }


def normalize_generation_output(value: str | dict[str, Any]) -> str:
    """Return the provider-independent subject/body JSON contract."""
    if isinstance(value, dict):
        payload = value
    else:
        text = str(value).strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                raise ProviderError("AI provider output must contain a JSON object")
            try:
                payload = json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise ProviderError("AI provider returned malformed JSON") from exc
    if not isinstance(payload, dict):
        raise ProviderError("AI provider output must be a JSON object")
    if isinstance(payload.get("text"), str):
        return normalize_generation_output(str(payload["text"]))
    subject = payload.get("subject")
    body = payload.get("body")
    if not isinstance(subject, str) or not subject.strip():
        raise ProviderError("AI provider output requires a non-empty subject")
    if not isinstance(body, str) or not body.strip():
        raise ProviderError("AI provider output requires a non-empty body")
    return json.dumps(
        {"schema_version": 1, "subject": subject.strip(), "body": body.strip()},
        ensure_ascii=False,
    )


class FallbackAIProvider:
    """Priority-ordered provider chain with output validation and a small circuit breaker."""

    def __init__(
        self,
        providers: list[tuple[str, AIProvider]],
        *,
        failure_threshold: int = 2,
        cooldown_seconds: int = 60,
        strategy: str = "priority",
    ):
        if not providers:
            raise ProviderUnavailableError("No enabled AI provider profiles are configured")
        self.providers = providers
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(1, cooldown_seconds)
        if strategy not in {"priority", "round_robin", "parallel"}:
            raise ValueError("strategy must be priority, round_robin, or parallel")
        self.strategy = strategy
        self._cursor = 0
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}
        self._lock = threading.Lock()
        self.last_run: dict[str, Any] = {}

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        if self.strategy == "parallel":
            return self._generate_parallel(system_prompt=system_prompt, user_prompt=user_prompt)
        attempts: list[dict[str, str]] = []
        now = time.monotonic()
        ordered = list(self.providers)
        if self.strategy == "round_robin":
            with self._lock:
                start = self._cursor % len(ordered)
                self._cursor += 1
            ordered = ordered[start:] + ordered[:start]
        for profile_id, provider in ordered:
            with self._lock:
                open_until = self._open_until.get(profile_id, 0.0)
            if open_until > now:
                attempts.append({"profile_id": profile_id, "status": "circuit_open"})
                continue
            try:
                output = normalize_generation_output(
                    provider.generate(system_prompt=system_prompt, user_prompt=user_prompt)
                )
            except Exception as exc:
                with self._lock:
                    failures = self._failures.get(profile_id, 0) + 1
                    self._failures[profile_id] = failures
                    if failures >= self.failure_threshold:
                        self._open_until[profile_id] = time.monotonic() + self.cooldown_seconds
                attempts.append(
                    {"profile_id": profile_id, "status": "failed", "error": str(exc)[:500]}
                )
                continue
            with self._lock:
                self._failures[profile_id] = 0
                self._open_until.pop(profile_id, None)
            attempts.append({"profile_id": profile_id, "status": "used"})
            self.last_run = {"selected_profile_id": profile_id, "attempts": attempts}
            return output
        self.last_run = {"selected_profile_id": "", "attempts": attempts}
        details = "; ".join(
            f"{item['profile_id']}: {item.get('error', item['status'])}" for item in attempts
        )
        raise ProviderUnavailableError(f"All AI providers failed. {details}".strip())

    def _generate_parallel(self, *, system_prompt: str, user_prompt: str) -> str:
        now = time.monotonic()
        eligible = []
        attempts: list[dict[str, Any]] = []
        for profile_id, provider in self.providers:
            with self._lock:
                open_until = self._open_until.get(profile_id, 0.0)
            if open_until > now:
                attempts.append({"profile_id": profile_id, "status": "circuit_open"})
            else:
                eligible.append((profile_id, provider))
        if not eligible:
            self.last_run = {"selected_profile_id": "", "attempts": attempts}
            raise ProviderUnavailableError("All AI provider circuits are open")
        executor = ThreadPoolExecutor(max_workers=len(eligible), thread_name_prefix="offsetx-ai")
        futures = {
            executor.submit(provider.generate, system_prompt=system_prompt, user_prompt=user_prompt): profile_id
            for profile_id, provider in eligible
        }
        selected = ""
        output = ""
        try:
            for future in as_completed(futures):
                profile_id = futures[future]
                try:
                    candidate = normalize_generation_output(future.result())
                except Exception as exc:
                    attempts.append({"profile_id": profile_id, "status": "failed", "error": str(exc)[:500]})
                    continue
                selected = profile_id
                output = candidate
                attempts.append({"profile_id": profile_id, "status": "used"})
                break
        finally:
            for future in futures:
                if not future.done():
                    future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
        self.last_run = {"selected_profile_id": selected, "attempts": attempts}
        if output:
            return output
        raise ProviderUnavailableError("All parallel AI providers failed")


def load_provider_config(path: Path | str) -> ProviderConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProviderError("Provider configuration must be a JSON object")
    return ProviderConfig(
        provider_type=str(payload.get("provider_type", "")).strip(),
        model=str(payload.get("model", "")).strip(),
        api_key_env=str(payload.get("api_key_env", "")).strip(),
        base_url=str(payload.get("base_url", "")).strip(),
        timeout_seconds=max(1, min(int(payload.get("timeout_seconds", 60)), 300)),
        extra=dict(payload.get("extra") or {}),
    )


def _validate_http_url(value: str, *, allow_local: bool = True) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ProviderError("Provider base_url must be an http or https URL")
    if parsed.username or parsed.password:
        raise ProviderError("Provider base_url must not contain embedded credentials")
    if not allow_local and parsed.scheme != "https":
        raise ProviderError("Remote provider base_url must use https")
    if parsed.scheme == "http":
        hostname = (parsed.hostname or "").lower()
        is_loopback = hostname == "localhost"
        try:
            is_loopback = is_loopback or ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            pass
        if not is_loopback:
            raise ProviderError("Plain HTTP provider URLs are allowed only on loopback")
    return value.rstrip("/")


class _HttpProvider:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        api_key: str,
        session: Any | None = None,
    ):
        self.config = config
        self.api_key = api_key
        self.session = session or requests.Session()

    def _post(
        self, url: str, *, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout_seconds,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                last_error = ProviderError(
                    f"AI provider returned {response.status_code}: {response.text[:500]}"
                )
                if attempt < 2:
                    time.sleep(2**attempt)
                continue
            if not response.ok:
                raise ProviderError(
                    f"AI provider returned {response.status_code}: {response.text[:1000]}"
                )
            try:
                data = response.json()
            except ValueError as exc:
                raise ProviderError("AI provider returned a non-JSON response") from exc
            if not isinstance(data, dict):
                raise ProviderError("AI provider returned an invalid JSON response")
            return data
        raise ProviderError(f"AI provider request failed after retries: {last_error}")


class OpenAIResponsesProvider(_HttpProvider):
    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        base_url = _validate_http_url(
            self.config.base_url or "https://api.openai.com/v1", allow_local=False
        )
        payload: dict[str, Any] = {
            "model": self.config.model,
            "instructions": system_prompt,
            "input": user_prompt,
        }
        payload.update(self.config.extra.get("request", {}))
        data = self._post(
            f"{base_url}/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload=payload,
        )
        if isinstance(data.get("output_text"), str):
            return str(data["output_text"])
        pieces: list[str] = []
        for output in data.get("output", []):
            if not isinstance(output, dict):
                continue
            for content in output.get("content", []):
                if not isinstance(content, dict):
                    continue
                value = content.get("text") or content.get("output_text")
                if isinstance(value, str):
                    pieces.append(value)
        if pieces:
            return "\n".join(pieces)
        raise ProviderError("OpenAI response did not contain text output")


class AnthropicMessagesProvider(_HttpProvider):
    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        base_url = _validate_http_url(
            self.config.base_url or "https://api.anthropic.com/v1", allow_local=False
        )
        payload: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": int(self.config.extra.get("max_tokens", 1200)),
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        payload.update(self.config.extra.get("request", {}))
        data = self._post(
            f"{base_url}/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": str(
                    self.config.extra.get("anthropic_version", "2023-06-01")
                ),
                "Content-Type": "application/json",
            },
            payload=payload,
        )
        pieces = [
            str(block.get("text", ""))
            for block in data.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        if pieces:
            return "\n".join(pieces)
        raise ProviderError("Anthropic response did not contain text output")


class OpenAICompatibleProvider(_HttpProvider):
    """Adapter for Nvidia, local gateways, and Chat Completions-compatible APIs."""

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        if not self.config.base_url:
            raise ProviderError("openai_compatible requires base_url")
        base_url = _validate_http_url(self.config.base_url)
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        payload.update(self.config.extra.get("request", {}))
        data = self._post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload=payload,
        )
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                "OpenAI-compatible response did not contain a message"
            ) from exc

        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            return content

        # Reasoning models (NVIDIA Nemotron, DeepSeek R1 and similar) put their
        # working in `reasoning_content` and can leave `content` empty when the
        # answer is cut short. Returning the reasoning is better than raising —
        # and if that is empty too, say *why* rather than "no content".
        reasoning = message.get("reasoning_content") if isinstance(message, dict) else None
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning

        finish_reason = ""
        try:
            finish_reason = str(data["choices"][0].get("finish_reason", ""))
        except (KeyError, IndexError, TypeError):
            pass
        if finish_reason == "length":
            raise ProviderError(
                "The model ran out of room before it produced an answer. Raise "
                "max_tokens for this model in config/providers.yaml under "
                "request_options."
            )
        raise ProviderError(
            "OpenAI-compatible response did not contain message content"
            + (f" (finish_reason: {finish_reason})" if finish_reason else "")
        )


class TemplateEngineHttpProvider(_HttpProvider):
    """Normalized adapter for the future separate template-intelligence application."""

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        if not self.config.base_url:
            raise ProviderError("template_engine_http requires base_url")
        base_url = _validate_http_url(self.config.base_url)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = self._post(
            f"{base_url}/v1/generate",
            headers=headers,
            payload={
                "schema_version": 1,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            },
        )
        if isinstance(data.get("text"), str):
            return str(data["text"])
        if isinstance(data.get("subject"), str) and isinstance(data.get("body"), str):
            return json.dumps({"subject": data["subject"], "body": data["body"]})
        raise ProviderError("Template engine response requires text or subject and body")


class CommandAIProvider:
    """Run a trusted local adapter over JSON stdin/stdout without a network server."""

    def __init__(self, config: ProviderConfig):
        command = config.extra.get("command")
        if not isinstance(command, list) or not command:
            raise ProviderError("local_command requires extra.command as a non-empty list")
        self.command = [str(part) for part in command]
        self.timeout_seconds = config.timeout_seconds

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        payload = json.dumps(
            {"schema_version": 1, "system_prompt": system_prompt, "user_prompt": user_prompt},
            ensure_ascii=False,
        )
        completed = subprocess.run(
            self.command,
            input=payload,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise ProviderError(
                f"Local AI command failed with exit code {completed.returncode}: "
                f"{completed.stderr[:500]}"
            )
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderError("Local AI command must return JSON") from exc
        text = result.get("text") or result.get("output")
        if not isinstance(text, str):
            raise ProviderError("Local AI command JSON must contain text or output")
        return text


def create_provider(
    config: ProviderConfig,
    *,
    environ: dict[str, str] | None = None,
    session: Any | None = None,
) -> AIProvider:
    provider_type = config.provider_type.lower()
    if provider_type == "local_command":
        return CommandAIProvider(config)

    env = environ if environ is not None else os.environ
    api_key = env.get(config.api_key_env, "").strip() if config.api_key_env else ""
    if provider_type == "template_engine_http":
        return TemplateEngineHttpProvider(config, api_key=api_key, session=session)
    if not api_key:
        raise ProviderError(
            f"Missing AI credential. Set the local environment variable: {config.api_key_env}"
        )
    if not config.model:
        raise ProviderError("AI provider model is required")
    if provider_type == "openai":
        return OpenAIResponsesProvider(config, api_key=api_key, session=session)
    if provider_type == "anthropic":
        return AnthropicMessagesProvider(config, api_key=api_key, session=session)
    if provider_type == "openai_compatible":
        return OpenAICompatibleProvider(config, api_key=api_key, session=session)
    raise ProviderError(f"Unsupported AI provider type: {config.provider_type}")
