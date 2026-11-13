## What and why

<!-- One or two sentences. Link the issue if there is one. -->

## How it was checked

- [ ] `cd backend && ruff check app tests && pytest -q`
- [ ] `cd frontend && npm run typecheck && npm test` (if the UI changed)
- [ ] A test covers the new behaviour or the bug (new audit rule: catalogue entry, check and test)

## Notes for the reviewer

<!-- Behaviour changes, new settings, anything that needs documenting in README, CHANGELOG or KNOWN_LIMITATIONS. -->

Numbers shown in the UI must stay honest: measured, imported, estimated or unavailable, never guessed.
