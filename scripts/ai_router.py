"""
Central AI routing module. All scripts import call_ai() from here.
No API keys are stored here — the key is always passed as a parameter.

Every supported provider except Anthropic speaks the OpenAI chat-completions
format, so a single OpenAI-compatible client handles Groq, OpenRouter, OpenAI
and any user-supplied "custom" endpoint. Anthropic uses its own SDK.
"""

import time

# Provider catalogue. base_url / model are filled at runtime for "custom".
PROVIDER_CONFIG = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "sdk": "openai",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "sdk": "openai",
    },
    "openai": {
        "base_url": None,            # use the SDK default
        "model": "gpt-4o",
        "sdk": "openai",
    },
    "anthropic": {
        "base_url": None,
        "model": "claude-opus-4-8",  # latest, most capable Claude model
        "sdk": "anthropic",
    },
    "custom": {
        "base_url": None,            # populated at runtime from user input
        "model": None,               # populated at runtime from user input
        "sdk": "openai",             # all custom providers must be OpenAI-compatible
    },
}

MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 5
MAX_TOKENS = 4096


def get_model_name(provider: str, custom_model: str = None) -> str:
    """Return the model string that will actually be sent for this provider."""
    if provider == "custom":
        return custom_model
    if provider not in PROVIDER_CONFIG:
        raise ValueError(f"Unknown provider: '{provider}'")
    return PROVIDER_CONFIG[provider]["model"]


def call_ai(
    prompt: str,
    provider: str,
    api_key: str,
    custom_base_url: str = None,
    custom_model: str = None,
) -> str:
    """
    Send a single prompt to the chosen provider and return the text response.

    Raises:
        ValueError      on unknown provider, missing custom config, or 401 auth failure
        ConnectionError on network failure
    """
    if provider not in PROVIDER_CONFIG:
        raise ValueError(
            f"Unsupported provider '{provider}'. "
            f"Choose one of: {', '.join(PROVIDER_CONFIG)}"
        )

    if not api_key:
        raise ValueError(f"No API key supplied for provider '{provider}'.")

    config = PROVIDER_CONFIG[provider]

    if provider == "custom":
        if not custom_base_url or not custom_model:
            raise ValueError(
                "Custom provider requires both a base URL and a model name."
            )
        return _call_openai_compatible(
            prompt, api_key, custom_base_url, custom_model, provider
        )

    if config["sdk"] == "anthropic":
        return _call_anthropic(prompt, api_key, config["model"])

    # groq / openrouter / openai
    return _call_openai_compatible(
        prompt, api_key, config["base_url"], config["model"], provider
    )


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
