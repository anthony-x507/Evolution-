# Public Safety Boundaries

This repository is public. It must stay clean.

## Never Commit

- API keys, tokens, passwords, cookies, sessions, or secrets.
- `.env` files.
- Keychain exports.
- Hermes profile configs.
- ABACO live files.
- Gateway configs.
- Telegram bot tokens.
- launchd plists.
- macOS firewall, TCC, Local Network, or Thunderbolt settings.
- Logs that contain private machine names, tokens, emails, phone numbers, or
  account data.
- Full cloned source trees from research candidates.

## Allowed In This Repo

- Original Rocket code.
- Public-safe architecture docs.
- Synthetic fixtures.
- Offline simulator outputs.
- Test plans.
- Dashboard data contracts with fake data.
- License and attribution notes.

## First Implementation Boundary

The first implementation slice must be offline only:

- synthetic nodes;
- synthetic routes;
- synthetic jobs;
- no real network checks;
- no system changes;
- no persistent process;
- no dashboard live edit;
- no Hermes or ABACO change.
