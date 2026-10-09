# ccbar

**ccbar** is a quiet status band above the prompt, drawn natively by Claude Code's function hooks. Nothing runs outside
the session: no `statusLine` command, no polling process.

```
  Opus 5.5 xhigh  ·  emaballarin/ccplugins ⎇ main (+12 −3)  ·  ██████░░░░░░░░░░░░░░░░░▒ 246k/1M (25%)  ·  Tok Σ 2.4M  ·  Session 9% (4h 21m) · Weekly 27% (2d 3h 7m)
```

Here `█` stands for the used window, `░` for the free track and `▒` for the auto-compaction reserve; the band draws all
three as coloured cells, not as these glyphs. Groups are joined by one faint `·` and packed into rows by measured
width; the rate-limit windows (`Session`, `Weekly`, and `Spend` behind a gateway) form one group, joined by a closer
`·`, so they always wrap together. On a narrower terminal the bar first shrinks from 24 to 16 cells (and further below
36 columns); only then does the band wrap, always between whole groups. Wrapped rows hang under the first row's second
segment, unless the indent would cost a row or leave a group too wide for the room beside it: then the whole band wraps
flush left. Below about 45 columns the joined limits no longer fit a row and are cut off at its end.

## Install

```
/plugin marketplace add emaballarin/ccplugins
/plugin install ccbar@ccplugins
```

### Requirements

- **Claude Code with function hooks enabled.** The function-hook API is early access and can change between releases.
  ccbar was built against Claude Code 2.1.288 and checked on 2.1.289 and 2.1.295. Function hooks also sit behind a rollout switch. Where it is off, ccbar
  does not load, and Claude Code says so in the debug log (`claude --debug`).
- **The terminal or the desktop app.** These are the two surfaces that draw the band above the prompt.
- **`git`, and `sh`, `tail`, `head`, `wc` and `tr`** (Linux, macOS; `head -c` is GNU and BSD, not POSIX). Without `git`
  the repository group is absent; without the others the token total is.

ccbar coexists with a `statusLine` command such as ccstatusline: that one draws under the prompt, ccbar above it.

### Settings

Two, in `/config` (stored under `pluginConfigs` in settings):

- **Token total (Tok Σ)** (`tokens`, `new` by default). `new` counts new tokens, as described under What it shows.
  `metered` adds the cache reads the transcripts record, each response still counted once. It still differs from
  ccstatusline's `Total`, which counts each transcript line of a response but reads the main transcript only. Changing it rescans the transcript.
- **Clickable repository and branch** (`links`, off by default) draws the GitHub `owner/name` as a link to the
  repository and the branch as a link to its `tree/<branch>` page. Turn it on only where Claude Code itself detects OSC
  8 hyperlinks: if the links in its replies are clickable, it does. Where it does not, each link prints its URL after
  its text and pushes the rest of the band off the row (see Design notes). Konsole and foot draw OSC 8 but are not
  detected; `FORCE_HYPERLINK=1` in the environment makes Claude Code treat a terminal as capable.

## What it shows

| Group          | Example                                       | Definition                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| -------------- | --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Model          | `Opus 5.5 xhigh`                              | The main loop's model by name. The effort level follows while extended thinking is on, and nothing follows while it is off.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Repository     | `emaballarin/ccplugins ⎇ main (+12 −3)`       | GitHub `owner/name` from the `origin` remote (nothing for other hosts), the branch (`@<sha>` when detached), and inserted/deleted lines from `git diff-files --shortstat` plus `git diff-index --cached --shortstat` against `HEAD` (the empty tree before the first commit), which never touch the index. `(+0 −0)` is a clean tree; when git cannot read the tree the counter is left out, never shown as clean. Untracked files are not counted. With `links` on (see Settings), `owner/name` links to the GitHub repository and the branch to its `tree/<branch>` page; a detached `@<sha>` is not linked.                                                                                           |
| Context        | `██████░░░░░░░░░░░░░░░░░▒ 246k/1M (25%)`      | Input tokens the last API response was answered over (uncached, cache write and cache read) against the model's window. The percentage is Claude Code's own; its colour measures load against the auto-compaction point, not against the window.                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Session tokens | `Tok Σ 2.4M`                                  | **New tokens**: uncached input + cache write + output over every API response of the session, subagents included, **counted once per response**, at the largest value any of its transcript lines records. Cache reads, the conversation re-sent with every request, are left out unless `tokens` is `metered` (see Settings). A cache write after the cache has expired (after 5 minutes or an hour idle, depending on the cache lifetime in use) counts the rewritten history again. Subagent transcripts record their responses only as streaming lines, with the output count at the last update written, so a subagent's output tokens can read low; its input and cache-write counts are complete. |
| Rate limits    | `Session 9% (4h 21m) · Weekly 27% (2d 3h 7m)` | `Session` is the five-hour window, `Weekly` the seven-day one: usage as the last API response reported it, and the time to reset, to the minute. Behind a Claude gateway, `Spend` shows the spend limit, which can pass 100%. Absent off a subscription.                                                                                                                                                                                                                                                                                                                                                                                                                                                 |

## Colours

Every colour is a Claude Code theme key, so the band follows the light or dark theme. The swatches below describe the
default dark theme.

### Text: one colour, one meaning

| Colour                | Theme key                           | Means                                              | Used for                                                   |
| --------------------- | ----------------------------------- | -------------------------------------------------- | ---------------------------------------------------------- |
| clay                  | `claude`                            | identity: which model                              | the model name                                             |
| lavender              | `permission`                        | a mode setting                                     | the effort level                                           |
| green → amber → red   | `success` → `warning` → `error`     | load against a cap: below 60%, below 85%, from 85% | context %, `Session` %, `Weekly` %                         |
| diff green / diff red | `diffAddedWord` / `diffRemovedWord` | lines added / removed (dim when zero)              | `(+12 −3)`                                                 |
| default               | —                                   | a plain value                                      | used tokens, the `Tok Σ` count, repository name, branch    |
| light grey            | `inactive`                          | labels, units, secondary figures                   | `/1M`, `Tok Σ`, `Session`, `Weekly`, countdowns, the owner |
| dark grey             | `subtle`                            | structure                                          | the `·` separators                                         |

### The context bar

The bar spans the model's whole window, left to right. Its used part has the exact length the API reported. That part is
split between the `/context` categories, in `/context`'s order and in `/context`'s own colours, so the bar reads like a
one-row `/context`. The split is Claude Code's local estimate (`breakdown: "summary"`), recomputed after every main-loop
turn. Category boundaries are drawn to an eighth of a cell.

| Colour (dark theme) | Theme key                   | `/context` category                                      |
| ------------------- | --------------------------- | -------------------------------------------------------- |
| mid grey            | `promptBorder`              | System prompt                                            |
| light grey          | `inactive`                  | System tools                                             |
| cyan                | `cyan_FOR_SUBAGENTS_ONLY`   | MCP tools                                                |
| green               | `green_FOR_SUBAGENTS_ONLY`  | MCP server instructions                                  |
| lavender            | `permission`                | Custom agents                                            |
| clay                | `claude`                    | Memory files                                             |
| amber               | `warning`                   | Skills                                                   |
| violet              | `purple_FOR_SUBAGENTS_ONLY` | Messages                                                 |
| darkest grey        | `userMessageBackground`     | Free space                                               |
| dark grey           | `subtle`                    | Auto-compaction reserve: compaction runs where it starts |

Deferred tool schemas are loaded on demand and sit outside the window, so the bar leaves them out, as `/context`'s grid
does. Until the first breakdown arrives, the used part is drawn in light grey (`inactive`).

## Refresh and cost

| Trigger                           | Refreshes                                                                |
| --------------------------------- | ------------------------------------------------------------------------ |
| Session start, main-loop turn end | everything, including the `/context` category split                      |
| Subagent turn end                 | the session-token total                                                  |
| Every 60 s                        | everything but the category split, so countdowns and limits stay current |

Each source also keeps a minimum gap, so a burst of events folds into one run:

| Source                    | Gap  |
| ------------------------- | ---- |
| in-process reads          | 5 s  |
| transcript tally          | 10 s |
| git                       | 15 s |
| `/context` category split | 30 s |

An idle minute costs a few in-process calls, plus four `git` processes inside a repository (five before its first
commit). One `sh` process is added only if the transcript has grown since the last read. Before a session's first
response its transcript does not exist yet; if it is not where the session root says, every project folder is searched
for it at most once in 5 minutes.

## Design notes

- **Why above the prompt.** ccbar would ideally sit where a `statusLine` command draws. That area is not one of the
  function-hook drawing sites. The nearest site under the prompt, `PromptHint`, is mounted _below_ Claude Code's
  mode-and-hint row (`⏵⏵ auto mode on`), so it would draw one row lower than a status line does. The band above the
  prompt is the native place left. If the under-prompt route is ever taken, the tree must keep core's
  `{ type: "engine" }` element, which is what `next(e)` returns. With that element in place, Claude Code keeps its own
  hint row live and only adds the plugin's rows. Without it, the plugin "stands in", and Claude Code swaps its row for a
  static dim copy of the hint.
- **What `Tok Σ` counts by default, and why it is far below ccstatusline's `Total`.** Within one API response the usage fields do
  not overlap: uncached input, cache write and cache read split the prompt, and output comes on top. Across responses
  they do: every request re-sends the whole conversation, mostly as cache reads, so a sum that includes them counts
  the history once per request. On the session measured, cache reads were 97.9% of the metered 115.7M tokens, against
  2.4M new; they are also billed at about a tenth of the input price, so the metered sum says little about cost or limits
  (the `Session` and `Weekly` percentages say that). By default ccbar counts new tokens only; `tokens: metered` adds the cache reads. ccstatusline 2.2.30 counts cache
  reads and, besides, sums every transcript line: a session transcript writes one line per content block, each
  repeating its response's full usage, which puts it a further 2.1–2.3× over on the sessions measured. ccbar counts each
  `message.id` once, at the largest value its lines record for each count, and adds only the rise when a later line
  raises it. Finished main-loop responses repeat the same counts on every line, so this equals counting each once.
  Subagent responses are written only as streaming lines (`stop_reason` null) that are never closed: counting only
  finished lines would miss about nine in ten of them.
- **Reading the transcript.** `$.fs.read` and `$.process.run` both stop at 4 MiB, but transcripts grow far past that.
  ccbar keeps a byte cursor per file (main transcript and each subagent's) and reads only the new whole lines, in 2 MiB
  ranges. A line longer than a range is stepped over by byte counts (`wc`), never by decoded text, which cannot say how
  many bytes a split character held; a response on such a line goes uncounted. A range that reads empty or reports an
  error is an error, never a skip. A reload rescans from the start.
- **Effort.** Taken from the last main-loop turn's `Stop` hook input, which is the level actually used, after any
  downgrade for the model. Before the first turn ends it falls back to the `effortLevel` setting. Whether thinking is on comes from the `/config` row `thinking`.
- **Links.** The repository and branch are drawn as `Link` elements: an OSC 8 hyperlink on the terminal, an anchor on
  desktop. In the fullscreen terminal a plain click may be taken by Claude Code itself; a ctrl- or alt-click opens the
  link. A terminal Claude Code does not credit with OSC 8 (Apple Terminal, xterm, Konsole, foot, screen, tmux before
  3.4) draws each link's text followed by its URL in dim. The band measures text only, so the two URLs (about 90
  columns) push the row's end off: at 160 columns the context bar, tokens and rate limits are lost. That is why `links`
  is off by default. The branch link is built from the local branch name and does
  not check that it exists on GitHub: an unpushed branch opens a 404.
- **Footprint.** Four hooks: `session.start`, `turn.complete` and `classic.Stop` observe and pass on; `ui.render` draws
  the band and gives way to surveys. Nothing touches tool calls or prompts. The transcript gets one dim notice line per
  distinct error, and nothing else.

## Development

Load the working copy with `claude --plugin-dir plugins/ccbar`. Claude Code then lays this build's API typings under
`.claude-plugin/types/` (git-ignored); `tsconfig.json` extends them. Edits hot-reload at each turn end.

```
claude plugin validate plugins/ccbar
claude plugin test plugins/ccbar
tsc -p plugins/ccbar
```

These checks need Claude Code itself and are not part of the repository's CI, which is Python-only: run all three
before a release. One rule the validator enforces trips most first attempts. `$` is never stored, passed to a
function of your own, or returned; it is only ever spelled `$.noun.method(…)` where it is called. The state helpers
`read` and `update` are the exception. That is why the refreshers are closures inside the `session.start` hook.
