#!/usr/bin/env bash

# This script runs during the Render build phase.
# It reconstructs the Google credentials file from a base64 environment variable.

# Fail fast if the variable is missing
if [ -z "$GOOGLE_CREDENTIALS_JSON" ]; then
  echo "❌ GOOGLE_CREDENTIALS_JSON is not set!"
  exit 1
fi

# Decode the base64 string into a JSON file
echo "$GOOGLE_CREDENTIALS_JSON" | base64 -d > google_credentials.json

echo "✅ google_credentials.json file created."
