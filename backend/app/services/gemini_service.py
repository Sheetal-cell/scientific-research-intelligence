"""Shared model routing: Groq first, with Gemini as the provider fallback."""
import os
from types import SimpleNamespace


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
            print(
                "[Groq] Structured schema request was rejected; "
                f"retrying in JSON mode: {schema_error}"
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
    """Try Groq first, then the primary and secondary Gemini models."""
    groq_error = None
    try:
        return _generate_with_groq(contents, config)
    except Exception as error:
        groq_error = error
        print(
            "[Groq] Primary provider failed; switching to Gemini. "
            f"Reason: {groq_error}"
        )

    primary_error = None
    try:
        print(f"[Gemini] Trying fallback provider model {primary_model}.")
        return client.models.generate_content(
            model=primary_model,
            contents=contents,
            config=config,
        )
    except Exception as error:
        primary_error = error
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

    try:
        return client.models.generate_content(
            model=fallback_model,
            contents=contents,
            config=config,
        )
    except Exception as fallback_error:
        raise RuntimeError(
            "All configured LLM providers failed. "
            f"Groq error: {groq_error}; "
            f"Gemini primary error: {primary_error}; "
            f"Gemini secondary error: {fallback_error}"
        ) from fallback_error
