#!/usr/bin/env python3
"""
Script to generate a test token for load testing.
This token will have the necessary scopes for the load tests.
"""

import os
import sys
from pathlib import Path

# Add the garden-backend-service to the Python path
sys.path.append(str(Path(__file__).parent.parent / "garden-backend-service"))

from src.auth.globus_auth import get_service_token, introspect_token


def main():
    # Ensure we're in test mode
    os.environ["GARDEN_ENV"] = "test"

    # Check for required environment variables
    required_vars = ["API_CLIENT_ID", "API_CLIENT_SECRET", "GARDEN_DEFAULT_SCOPE"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(
            f"Error: Missing required environment variables: {', '.join(missing_vars)}",
            file=sys.stderr,
        )
        return 1

    try:
        # Get the token
        token = get_service_token()

        # Verify the token works by introspecting it
        token_info = introspect_token(token, log=False)

        # Print debug info if requested
        if os.getenv("DEBUG"):
            print("Token info:", file=sys.stderr)
            print(f"  Identity: {token_info.get('sub')}", file=sys.stderr)
            print(f"  Username: {token_info.get('username')}", file=sys.stderr)
            print(f"  Email: {token_info.get('email')}", file=sys.stderr)
            print(f"  Scopes: {token_info.get('scope')}", file=sys.stderr)

        # Print just the token for use in Artillery
        print(token)
        return 0

    except Exception as e:
        print(f"Error getting test token: {str(e)}", file=sys.stderr)
        if os.getenv("DEBUG"):
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
