"""Shared Gemini request helper with a lightweight model fallback."""
import os


def generate_with_fallback(client, primary_model, contents, config):
    """Use the configured model, falling back on transient 503 capacity errors."""
    try:
        return client.models.generate_content(
            model=primary_model,
            contents=contents,
            config=config,
        )
    except Exception as error:
        message = str(error).upper()
        if "503" not in message and "UNAVAILABLE" not in message:
            raise

        fallback_model = os.getenv(
            "GEMINI_FALLBACK_MODEL",
            "gemini-3.1-flash-lite",
        ).strip()

        if not fallback_model or fallback_model == primary_model:
            raise

        print(
            f"[Gemini] {primary_model} is temporarily unavailable; "
            f"trying fallback model {fallback_model}."
        )
        return client.models.generate_content(
            model=fallback_model,
            contents=contents,
            config=config,
        )
