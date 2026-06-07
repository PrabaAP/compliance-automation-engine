"""
Tests AI provider connection with a given API key.
Called by the dashboard to validate before running analysis.

Usage:
    python scripts/01_test_connection.py --provider groq --key YOUR_KEY
    python scripts/01_test_connection.py --provider custom --key KEY \\
        --base-url https://api.example.com/v1 --model my-model
"""

import argparse
import os
import sys

# Ensure sibling modules (ai_router) import cleanly regardless of CWD.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_router import call_ai, get_model_name  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Validate an AI provider connection.")
    parser.add_argument("--provider", required=True, help="groq | openrouter | anthropic | openai | custom")
    parser.add_argument("--key", required=True, help="API key for the chosen provider")
    parser.add_argument("--base-url", default=None, help="Base URL (custom provider only)")
    parser.add_argument("--model", default=None, help="Model name (custom provider only)")
    args = parser.parse_args()

    try:
        reply = call_ai(
            prompt="Respond with exactly: Connected.",
            provider=args.provider,
            api_key=args.key,
            custom_base_url=args.base_url,
            custom_model=args.model,
        )
        model_name = get_model_name(args.provider, args.model)
        print(f"✅ {args.provider} connected · model: {model_name}")
        # The reply itself is not asserted on; providers phrase confirmations
        # differently. A clean return from call_ai is the success signal.
        if reply:
            print(f"   Response: {reply.strip()[:80]}")
        sys.exit(0)
    except (ValueError, ConnectionError) as exc:
        print(f"❌ {args.provider} connection failed: {exc}")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ {args.provider} connection failed (unexpected error): {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
