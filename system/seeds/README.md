# Initialization Seeds

Seeds are blank, system-owned inputs used by `career-os init`. They never contain a real person's data and are never synchronized over initialized user records.

`data-root-readme.md` is the user-facing Career Home router. Initialization
copies it once to the configured data-root `README.md`; an existing user home is
never adopted or overwritten.

`authorities/` contains one English initialization README per canonical domain.
Each defines Key Terms, Authority Map, Lifecycle, Change Rules, and a Completion
Gate. Initialization copies the matching file once; the resulting README belongs
to the user data layer and may evolve with that user's multilingual Vault.
