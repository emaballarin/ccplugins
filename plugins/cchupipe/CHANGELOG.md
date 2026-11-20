# Changelog

All notable changes to the `hup` plugin are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## 0.2.2 — 2026-11-20

Housekeeping — coordinated marketplace version alignment alongside the `mf` 0.8.4 release (`AGENTS.md` re-synced) and
the `ccsci` 0.10.3 release (four skill descriptions that route, a note in `deep-researcher`). Nothing in this plugin
was edited since 0.2.1. No hook logic changed.

## 0.2.1 — 2026-11-20

First release (0.1.0 to 0.2.0 were local development builds). Pipes the heads-ups of Claude Code's built-in "You
should know" plugin to the main agent.

- **Capture.** Hooks the built-in plugin's own `$.store` writes and reads of its `sessions` key, so each new heads-up
  is caught as it is written, and one already on screen when hup loads is caught at the next redraw. No extra model
  call, no file reads. The record is checked whenever it is written: one hup cannot read (not a list, no entry with an
  id, a view kind the plugin itself does not know, an offer without line or time) is skipped and counted, with one
  toast. An error while handling a heads-up, hiding one or registering the lookup tool goes to the debug log, and
  the first one also gets a toast.
- **Push.** A new heads-up is appended to the main conversation with `$.session.append`, so the main agent reads it
  behind its next tool result, mid-turn. The note carries the line only, says the heads-up is not the person's words
  and is sometimes wrong, and asks the agent to check the claim before acting on it, fix what is its own, raise
  what is the person's, and report it in its next message. A note another plugin refuses, or that fails to send, is
  recorded as not sent.
- **Lookup.** `mcp__hup__heads_up` lists this session's heads-ups with their explainers, or one by number; the full
  list ends with how many times the built-in plugin wrote its record and how many records hup skipped.
- **Swallow** (`swallow`, on by default). Once the main loop's next request carries the note, the heads-up is hidden:
  the built-in plugin reads it as gone, so it leaves the screen and is never counted as typed past unanswered (that
  count makes the side agent check less often). A heads-up whose push failed stays on screen. Claude then tells you
  about it in its next message; it may leave out only a slip in its own work it has simply fixed, or a passing
  mishap, never one that questions your work or choices, a choice of its own that changes what you get, or a decision
  that is yours, now or later.
- **Policy** (`push`): `all` (default), `heads-up` ("Heads up" only), `none`.
