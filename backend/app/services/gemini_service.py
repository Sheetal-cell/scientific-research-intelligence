"""Shared model routing: Groq first, with Gemini as the provider fallback."""
import os
import re
import time
from types import SimpleNamespace

# Groq free/on-demand limits are tight. Avoid sending oversized prompts and
# pause Groq briefly after a rate-limit response so every next agent call does
# not immediately hit the same limit.
GROQ_MAX_PROMPT_CHARS = int(os.getenv("GROQ_MAX_PROMPT_CHARS", "8000"))
GROQ_COOLDOWN_SECONDS = int(os.getenv("GROQ_COOLDOWN_SECONDS", "60"))
_groq_cooldown_until = 0.0
_gemini_primary_cooldown_until = 0.0
_gemini_fallback_cooldown_until = 0.0
_gemini_primary_quota_error = None
_gemini_fallback_quota_error = None


def _retry_delay_seconds(message, default_seconds):
    """Read provider retry hints such as '9m33s' or '45968s'."""
    text = str(message).lower()
    seconds_match = re.search(r"(\\d+(?:\\.\\d+)?)\\s*s", text)
    if seconds_match:
        return max(1, int(float(seconds_match.group(1))))

    hours = re.search(r"(\\d+)\\s*h", text)
    minutes = re.search(r"(\\d+)\\s*m", text)
    seconds = re.search(r"(\\d+)\\s*s", text)
    total = (
        (int(hours.group(1)) * 3600 if hours else 0)
        + (int(minutes.group(1)) * 60 if minutes else 0)
        + (int(seconds.group(1)) if seconds else 0)
    )
    return total if total else default_seconds


def _is_daily_quota_exhausted(error):
    message = str(error).lower()
    return any(marker in message for marker in (
        "tokens per day",
        "requests per day",
        "perdayperproject",
        "perdaypermodel",
        "daily quota",
        "quota exceeded for metric",
    ))


def _gemini_is_daily_quota_error(error):
    message = str(error).lower()
    return _is_daily_quota_exhausted(message) or (
        "resource_exhausted" in message and "retry" in message
    )


def _is_groq_rate_limit(error):
    message = str(error).lower()
    status_code = getattr(error, "status_code", None)
    return (
        status_code in (413, 429)
        or "rate_limit_exceeded" in message
        or "tokens per minute" in message
        or "request too large" in message
    )


def _generate_with_groq(contents, config):
    """Run the JSON task on Groq and return a Gemini-like response object."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured. Add a Groq API key to backend/.env "
            "to use Groq as the primary provider."
        )

    from groq import Groq

    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
    schema_type = getattr(config, "response_schema", None)
    schema = None

    if schema_type is not None:
        if hasattr(schema_type, "model_json_schema"):
            schema = schema_type.model_json_schema()
        elif isinstance(schema_type, dict):
            schema = schema_type

    client = Groq(api_key=api_key)
    prompt = contents if isinstance(contents, str) else str(contents)

    request = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Follow the user's instructions exactly. Return only a "
                    "valid JSON object. Do not invent facts, citations, "
                    "evidence, or numerical results."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }

    # Use best-effort JSON Schema where supplied. If the provider rejects a
    # schema feature, retry once in JSON-object mode and validate with Pydantic.
    if schema:
        try:
            response = client.chat.completions.create(
                **{
                    **request,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": getattr(schema_type, "__name__", "research_output").lower(),
                            "strict": False,
                            "schema": schema,
                        },
                    },
                }
            )
        except Exception as schema_error:
            error_text = str(schema_error).lower()
            status_code = getattr(schema_error, "status_code", None)
            is_rate_limit = (
                status_code in (413, 429)
                or "rate_limit_exceeded" in error_text
                or "tokens per minute" in error_text
            )
            if is_rate_limit:
                # Do not immediately repeat a request that Groq has rejected
                # for rate limiting. Let generate_with_fallback switch to Gemini.
                raise

            # A schema parse failure means Groq could not produce valid
            # structured output. Retrying the same prompt in JSON mode often
            # returns unstructured reasoning instead of the requested object.
            # Route this request to Gemini rather than accepting bad output.
            if (
                "output_parse_failed" in error_text
                or "parsing failed" in error_text
                or "failed_generation" in error_text
            ):
                raise RuntimeError(
                    "Groq could not produce valid structured JSON; "
                    "switching to Gemini."
                ) from schema_error

            # Only retry JSON-object mode for genuine schema/feature
            # compatibility errors, not arbitrary provider failures.
            unsupported_schema = any(
                marker in error_text
                for marker in (
                    "json_schema",
                    "response_format",
                    "not supported",
                    "unsupported",
                    "unknown parameter",
                    "invalid parameter",
                )
            )
            if not unsupported_schema:
                raise

            print(
                "[Groq] Schema feature unsupported; retrying once in JSON mode."
            )
            response = client.chat.completions.create(**request)
    else:
        response = client.chat.completions.create(**request)

    output = response.choices[0].message.content
    if not output:
        raise RuntimeError("Groq returned an empty response.")
    print(f"[Groq] Primary response generated successfully using {model}.")
    return SimpleNamespace(text=output)


def generate_with_fallback(client, primary_model, contents, config):
    """Use available providers, remembering quota exhaustion across agent calls."""
    global _groq_cooldown_until
    global _gemini_primary_cooldown_until, _gemini_fallback_cooldown_until
    global _gemini_primary_quota_error, _gemini_fallback_quota_error
    groq_error = None
    prompt_text = contents if isinstance(contents, str) else str(contents)
    now = time.monotonic()

    if len(prompt_text) > GROQ_MAX_PROMPT_CHARS:
        groq_error = (
            f"Prompt has {len(prompt_text)} characters; configured Groq "
            f"safe limit is {GROQ_MAX_PROMPT_CHARS}. Routing to Gemini."
        )
        print(f"[Groq] Skipping primary provider for oversized prompt. {groq_error}")
    elif now < _groq_cooldown_until:
        remaining = int(_groq_cooldown_until - now)
        groq_error = f"Groq rate-limit cooldown active for approximately {remaining}s."
        print(f"[Groq] {groq_error} Routing this request to Gemini.")
    else:
        try:
            return _generate_with_groq(contents, config)
        except Exception as error:
            groq_error = error
            if _is_groq_rate_limit(error):
                retry_seconds = _retry_delay_seconds(
                    error,
                    GROQ_COOLDOWN_SECONDS,
                )
                _groq_cooldown_until = time.monotonic() + retry_seconds
                print(
                    f"[Groq] Rate limit detected. Pausing Groq for "
                    f"{retry_seconds}s based on the provider retry hint."
                )
            print(
                "[Groq] Primary provider failed; switching to Gemini. "
                f"Reason: {groq_error}"
            )

    now = time.monotonic()
    if now < _gemini_primary_cooldown_until:
        remaining = int(_gemini_primary_cooldown_until - now)
        primary_error = RuntimeError(
            f"Gemini primary model quota cooldown active for approximately {remaining}s. "
            f"Previous error: {_gemini_primary_quota_error}"
        )
        print(f"[Gemini] Skipping primary model; quota cooldown active for {remaining}s.")
    else:
        primary_error = None

    if primary_error is None:
        try:
            print(f"[Gemini] Trying fallback provider model {primary_model}.")
            response = client.models.generate_content(
                model=primary_model,
                contents=contents,
                config=config,
            )
            return response
        except Exception as error:
            primary_error = error
            if _gemini_is_daily_quota_error(error):
                retry_seconds = _retry_delay_seconds(error, 3600)
                _gemini_primary_cooldown_until = time.monotonic() + retry_seconds
                _gemini_primary_quota_error = str(error)
                print(
                    f"[Gemini] Daily quota exhausted for {primary_model}. "
                    f"Skipping it for approximately {retry_seconds}s."
                )
            else:
                print(
                    f"[Gemini] {primary_model} failed; trying secondary model. "
                    f"Reason: {primary_error}"
                )

    fallback_model = os.getenv(
        "GEMINI_FALLBACK_MODEL",
        "gemini-3.1-flash-lite",
    ).strip()

    if not fallback_model or fallback_model == primary_model:
        raise RuntimeError(
            "Groq and the primary Gemini model failed, and no distinct "
            "GEMINI_FALLBACK_MODEL is configured."
        ) from primary_error

    now = time.monotonic()
    if now < _gemini_fallback_cooldown_until:
        remaining = int(_gemini_fallback_cooldown_until - now)
        fallback_error = RuntimeError(
            f"Gemini secondary model quota cooldown active for approximately {remaining}s. "
            f"Previous error: {_gemini_fallback_quota_error}"
        )
        raise RuntimeError(
            "All configured LLM providers are currently rate-limited. "
            f"Groq: {groq_error}; Gemini primary: {primary_error}; "
            f"Gemini secondary: {fallback_error}"
        ) from fallback_error

    try:
        return client.models.generate_content(
            model=fallback_model,
            contents=contents,
            config=config,
        )
    except Exception as fallback_error:
        if _gemini_is_daily_quota_error(fallback_error):
            retry_seconds = _retry_delay_seconds(fallback_error, 3600)
            _gemini_fallback_cooldown_until = time.monotonic() + retry_seconds
            _gemini_fallback_quota_error = str(fallback_error)
            print(
                f"[Gemini] Daily quota exhausted for {fallback_model}. "
                f"Skipping it for approximately {retry_seconds}s."
            )

        raise RuntimeError(
            "All configured LLM providers failed. "
            f"Groq error: {groq_error}; "
            f"Gemini primary error: {primary_error}; "
            f"Gemini secondary error: {fallback_error}"
        ) from fallback_error
