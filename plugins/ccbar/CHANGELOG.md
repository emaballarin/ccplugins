# Changelog

All notable changes to the `ccbar` plugin are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## 0.2.0 — 2026-10-05

- **`Tok Σ` counts new tokens**: uncached input, cache writes and output. Cache reads, the conversation re-sent with every request, are left out. They were 97.9% of the metered total on the session measured (115.7M against 2.4M new), so the figure now shows how far the conversation has grown rather than how often it was re-sent. Still counted once per response, subagents included. The number shown drops sharply on upgrade: that is the definition changing, not data lost.
- **`Session` and `Weekly` wrap together**: the rate-limit windows (`Spend` too, behind a gateway) form one group, joined by a closer `·`, so a narrow row no longer leaves `Weekly` alone on the next one. Below about 45 columns the joined group no longer fits a row and is cut off at its end.
- **Hanging indent**: wrapped rows start under the first row's second segment, unless the indent would cost a row or leave a group too wide for the room beside it; then the whole band wraps flush left.

## 0.1.0 — 2026-10-05

First release. A status band above the prompt, drawn through `ui.render` on `AbovePrompt`:

- **Model and effort**: the main loop's model by name (`Opus 5.5`), and the effort level while extended thinking is on.
- **Repository**: GitHub `owner/name`, branch (`@<sha>` when detached) and a staged-plus-unstaged diff counter read without touching the index: `(+0 −0)` on a clean tree, left out when git cannot read it.
- **Context**: a bar over the model's window, its used part coloured by the `/context` categories, then the free window and the auto-compaction reserve; `used/window (n%)`, the percentage coloured by load against the auto-compaction point.
- **Session tokens** (`Tok Σ`): input, output, cache read and cache write over every API response of the session, subagents included, counted once per response at the largest value its lines record (subagent responses are written only as streaming lines).
- **Rate limits**: `Session` and `Weekly` usage, coloured by load, with reset countdowns to the minute.
- **Layout**: groups joined by one faint `·`, packed into rows by measured width; the bar narrows before the band wraps.
- **Refresh**: a 60 s idle tick plus every turn end, each source paced by its own minimum gap.
