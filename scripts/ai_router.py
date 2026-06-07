"""
Central AI routing module. All scripts import call_ai() from here.
No API keys or model names are stored here — both are always passed as parameters.

Every supported provider except Anthropic speaks the OpenAI chat-completions
format, so a single OpenAI-compatible client handles Groq, OpenRouter, OpenAI
and any user-supplied "custom" endpoint. Anthropic uses its own SDK.

The user supplies their own model name at runtime; nothing is hardcoded.
"""

import time

# Provider catalogue.
# base_url is the fixed API endpoint for each hosted provider.
# Model names are NOT stored here — users supply them at runtime.
PROVIDER_CONFIG = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "sdk": "openai",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "sdk": "openai",
    },
    "openai": {
        "base_url": None,   # SDK default
        "sdk": "openai",
    },
    "anthropic": {
        "base_url": None,
        "sdk": "anthropic",
    },
    "custom": {
        "base_url": None,   # populated at runtime from user input
        "sdk": "openai",    # all custom providers must be OpenAI-compatible
    },
}

MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 5
MAX_TOKENS = 4096


def get_model_name(provider: str, model: str = None) -> str:
    """Return the model string that will be sent for this provider."""
    if provider not in PROVIDER_CONFIG:
        raise ValueError(f"Unknown provider: '{provider}'")
    return model or ""


def call_ai(
    prompt: str,
    provider: str,
    api_key: str,
    model: str,
    custom_base_url: str = None,
) -> str:
    """
    Send a single prompt to the chosen provider and return the text response.

    Args:
        prompt          The text prompt to send.
        provider        One of: groq, openrouter, anthropic, openai, custom.
        api_key         API key for the chosen provider.
        model           Model name (required — user-supplied, no defaults).
        custom_base_url Base URL for the custom provider only.

    Raises:
        ValueError      on unknown provider, missing config, or 401 auth failure.
        ConnectionError on network failure.
    """
    if provider not in PROVIDER_CONFIG:
        raise ValueError(
            f"Unsupported provider '{provider}'. "
            f"Choose one of: {', '.join(PROVIDER_CONFIG)}"
        )

    if not api_key:
        raise ValueError(f"No API key supplied for provider '{provider}'.")

    if not model:
        raise ValueError(
            f"No model name supplied for provider '{provider}'. "
            f"Enter a model name in the dashboard."
        )

    config = PROVIDER_CONFIG[provider]

    if provider == "custom":
        if not custom_base_url:
            raise ValueError("Custom provider requires a base URL.")
        return _call_openai_compatible(prompt, api_key, custom_base_url, model, provider)

    if config["sdk"] == "anthropic":
        return _call_anthropic(prompt, api_key, model)

    # groq / openrouter / openai
    return _call_openai_compatible(prompt, api_key, config["base_url"], model, provider)


def _call_openai_compatible(prompt, api_key, base_url, model, provider):
    """Handle any OpenAI chat-completions endpoint with timeout retries."""
    import openai

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = openai.OpenAI(**client_kwargs)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=MAX_TOKENS,
            )
            return response.choices[0].message.content
        except openai.APITimeoutError as exc:
            last_error = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_WAIT_SECONDS)
        except openai.AuthenticationError as exc:
            raise ValueError(
                f"Authentication failed for provider '{provider}' (401). "
                f"Check that your API key is correct and active."
            ) from exc
        except openai.APIConnectionError as exc:
            raise ConnectionError(
                f"Could not reach provider '{provider}'. "
                f"Check your network connection and base URL."
            ) from exc

    raise ConnectionError(
        f"Provider '{provider}' timed out after {MAX_RETRIES} attempts."
    ) from last_error


def _call_anthropic(prompt, api_key, model):
    """Handle the Anthropic Messages API with timeout retries."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            # content is a list of blocks; collect the text blocks.
            return "".join(
                block.text for block in message.content if block.type == "text"
            )
        except anthropic.APITimeoutError as exc:
            last_error = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_WAIT_SECONDS)
        except anthropic.AuthenticationError as exc:
            raise ValueError(
                "Authentication failed for provider 'anthropic' (401). "
                "Check that your API key is correct and active."
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise ConnectionError(
                "Could not reach provider 'anthropic'. Check your network connection."
            ) from exc

    raise ConnectionError(
        f"Provider 'anthropic' timed out after {MAX_RETRIES} attempts."
    ) from last_error
