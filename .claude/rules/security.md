# Security

- Never hardcode API keys, tokens, or credentials. Use environment variables.
- Never read, print, or log .env files, secrets, or credential files.
- Flag any destructive command (rm -rf, DROP, TRUNCATE) before running it.
- Validate all external input before using it.
- Do not commit files matching *secret*, *credentials*, or .env.*
