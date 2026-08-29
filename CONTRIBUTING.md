# Contributing to ScreenLink

Thanks for considering contributing — this project only works as a cross-platform tool if it gets eyes from people who use both Linux and Windows regularly. Bug reports, docs fixes, and code are all welcome.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Ways to Contribute](#ways-to-contribute)
- [Reporting Bugs](#reporting-bugs)
- [Proposing Features](#proposing-features)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Commit Message Convention](#commit-message-convention)
- [Pull Request Process](#pull-request-process)
- [Areas Especially Looking for Help](#areas-especially-looking-for-help)

## Code of Conduct

Be respectful, assume good faith, and keep discussion focused on the technical problem. Personal attacks, harassment, or discrimination of any kind aren't tolerated. If a `CODE_OF_CONDUCT.md` doesn't yet exist in this repo, adopting the [Contributor Covenant](https://www.contributor-covenant.org/) verbatim is a reasonable default — happy to take a PR for that too.

## Ways to Contribute

- **Code:** pick up an issue labeled `good first issue` or `help wanted`, or work through the implementation steps in [DEVELOPMENT.md](DEVELOPMENT.md) if the project is still early-stage.
- **Testing on real hardware:** especially different Windows laptop generations (older integrated GPUs decode H.264 very differently) and different Linux GPU vendors (Intel/AMD VAAPI vs. NVIDIA NVENC).
- **Documentation:** clarifying setup steps that tripped you up is genuinely high-value — you're the best-positioned person to spot what's confusing, right after you got confused by it.
- **Design/UX:** the client's connection and settings UI needs someone with product sense, not just protocol knowledge.

## Reporting Bugs

Before filing, search existing issues to avoid duplicates. Include:
1. **OS/version** for both the Linux server and Windows client (e.g. "Ubuntu 24.04, GNOME/X11" / "Windows 11 23H2").
2. **GPU** on both sides (relevant for hardware encode/decode issues).
3. **Steps to reproduce.**
4. **Server and client logs** — run with `--verbose` (or set `GST_DEBUG=3`, see [DEVELOPMENT.md §8](DEVELOPMENT.md#8-debugging-tips)) if the bug is video-pipeline related.
5. **Network setup** (Wi-Fi band, router, any VPN active) — a surprising number of connectivity bugs turn out to be router-specific mDNS/multicast filtering.

## Proposing Features

Open an issue tagged `enhancement` before writing code for anything non-trivial — this avoids duplicated effort and lets us confirm the feature fits the architecture (or discuss the ARCHITECTURE.md change it requires) before you invest time in an implementation.

## Development Workflow

1. Fork the repo and clone your fork.
2. Follow [DEVELOPMENT.md](DEVELOPMENT.md) to get both the server and client running locally.
3. Create a branch off `main`:
   - `feature/<short-description>` for new functionality
   - `fix/<short-description>` for bug fixes
   - `docs/<short-description>` for documentation-only changes
4. Make focused commits (see convention below).
5. Open a pull request against `main`.

## Coding Standards

- **Style:** [PEP 8](https://peps.python.org/pep-0008/), enforced via `black` (line length 100) and `ruff` for linting — both configured in `pyproject.toml`. Run `black . && ruff check .` before pushing.
- **Type hints:** required on all new function signatures; the codebase is gradually being annotated throughout.
- **Docstrings:** every public function/class gets a docstring explaining *why*, not just *what* — especially in the pipeline and protocol modules, where the "why" (e.g. "why UDP here, why TCP there") isn't obvious from the code alone. Link to the relevant [ARCHITECTURE.md](ARCHITECTURE.md) section where useful.
- **No bare `except:`** — catch specific exceptions; this codebase talks to sockets, GStreamer, and OS input APIs, all of which fail in specific, distinguishable ways that callers need to handle differently.
- **Tests:** new logic in `common/` or protocol-handling code requires unit tests; pipeline/OS-integration code should at minimum include a manual test procedure described in the PR if it can't be automated.

## Commit Message Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(client): add jitter buffer latency slider to settings panel
fix(server): tear down virtual display on ungraceful disconnect
docs(architecture): clarify RTP payload size vs MTU
refactor(protocol): extract message envelope into shared dataclass
```

Common prefixes: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`. This makes the changelog generatable and makes `git log` skimmable when tracking down when a specific behavior changed.

## Pull Request Process

1. **Keep PRs focused** — one logical change per PR. A PR that both refactors the protocol module *and* adds a new feature is hard to review and hard to revert safely.
2. **Reference the issue** it closes (`Closes #42`) where applicable.
3. **Describe what you tested and how**, especially for anything touching the capture, encode, decode, or input-injection paths — these are the parts that are hardest to unit test and easiest to silently break on a specific GPU/OS combination.
4. **CI must pass** (tests, `black --check`, `ruff`) before review.
5. Expect review feedback — this is a young project with an evolving architecture; back-and-forth on design is normal, not a sign something's wrong with your contribution.
6. Once approved, a maintainer will merge — please don't force-push after review has started unless asked to, since it breaks inline comment threads.

## Areas Especially Looking for Help

- Wayland virtual-output creation ([ARCHITECTURE.md §9](ARCHITECTURE.md#9-virtual-display-creation-on-linux)) — currently the biggest architectural gap.
- Optional TLS mode for the control/video channels ([ARCHITECTURE.md §14](ARCHITECTURE.md#14-security-model)).
- Real-hardware testing matrix across GPU vendors (issue template for structured latency/quality reports welcome).
- A Rust or C++ client rewrite once the protocol (§6–§8 of ARCHITECTURE.md) stabilizes — the protocol is intentionally kept plain JSON + standard RTP specifically to make this feasible later.

If you're not sure where to start, open a discussion thread or comment on an issue asking — that's genuinely welcome, not a bother.
