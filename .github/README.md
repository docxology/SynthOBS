# .github/

GitHub Actions configuration for the public SynthOBS repo: one workflow,
`workflows/verify.yml`, running the engine suite (figures + pytest at 90%
coverage + package smoke) and the native-parser behavioral parity test on
every push/PR. See AGENTS.md for the job details.

Part of the DataTools lane (local-only, never committed). Parent: `../README.md`.
