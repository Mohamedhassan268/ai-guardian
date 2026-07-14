#!/bin/bash
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r ".tool_input.command // empty")

if echo "$COMMAND" | grep -qE "(rm -rf /|DROP DATABASE|TRUNCATE)"; then
  echo "{\"decision\": \"block\", \"reason\": \"Destructive command blocked\"}"
  exit 2
fi

if echo "$COMMAND" | grep -qE "(cat.*\.env|echo.*PASSWORD|cat.*secret)"; then
  echo "{\"decision\": \"block\", \"reason\": \"Command may expose secrets\"}"
  exit 2
fi

echo "{\"decision\": \"allow\"}"
