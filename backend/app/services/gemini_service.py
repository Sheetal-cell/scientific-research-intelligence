"""Shared model routing: Gemini first, Groq as an independent emergency fallback."""
import os
from types import SimpleNamespace


def _generate_with_groq(contents, config):
    """Run the same JSON task on Groq and return a Gemini-like response object."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "Both configured Gemini models are unavailable and GROQ_API_KEY "
            "is not configured. Add a Groq API key to backend/.env for the "
            "independent backup provider."
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
    # schema feature, retry once in JSON-object mode and validate with Pydantic
    # in the calling agent.
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

    text = response.choices[0].message.content
    if not text:
        raise RuntimeError("Groq returned an empty response.")
    print(f"[Groq] Backup response generated successfully using {model}.")
    return SimpleNamespace(text=text)


def generate_with_fallback(client, primary_model, contents, config):
    """Try primary Gemini, secondary Gemini, then Groq if configured."""
    try:
        return client.models.generate_content(
            model=primary_model,
            contents=contents,
            config=config,
        )
    except Exception as primary_error:
        message = str(primary_error).upper()
        transient_markers = (
            "429", "500", "502", "503", "504",
            "RESOURCE_EXHAUSTED", "UNAVAILABLE", "INTERNAL",
        )
        if not any(marker in message for marker in transient_markers):
            raise

    fallback_model = os.getenv(
        "GEMINI_FALLBACK_MODEL",
        "gemini-3.1-flash-lite",
    ).strip()

    try:
        if not fallback_model or fallback_model == primary_model:
            raise RuntimeError("No distinct Gemini fallback model is configured.")

        print(
            f"[Gemini] {primary_model} is unavailable; "
            f"trying {fallback_model}."
        )
        return client.models.generate_content(
            model=fallback_model,
            contents=contents,
            config=config,
        )
    except Exception as fallback_error:
        print(
            "[Gemini] Both Gemini models failed; "
            f"trying independent Groq backup. Last Gemini error: {fallback_error}"
        )
        return _generate_with_groq(contents, config)
