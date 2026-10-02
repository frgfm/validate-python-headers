# Contributing to Lint My Headers

Follow the [code of conduct](CODE_OF_CONDUCT.md), [runtime contracts](README.md), and [contributor safety rules](AGENTS.md).

## Structure

- `rust/analysis.rs`: header recognition and proposed year replacements.
- `rust/filesystem.rs`: discovery, identity checks, and atomic writes.
- `rust/config.rs`, `rust/lib.rs`: configuration, command execution, and output.
- `tests/cli.rs` and Rust module tests: CLI and safety regression coverage.
- `src/lint_my_headers`: optional Python launcher and pinned SPDX source data.
- `src/tests`, `.github/`, `scripts/`: release checks and maintainer tooling.
- `.agents/skills/lint-my-headers`: agent instructions and historical eval assets.

## Local development

Use the Rust toolchain pinned in `rust-toolchain.toml`, a C compiler for Tree-sitter, Python 3.11+, and uv. Work on a feature branch.

```shell
make install-quality
make test
make quality
make package-check
uv run --no-sync --group quality prek run --all-files
uv run --no-sync --group quality prek try-repo . lmh --all-files
git diff --check
```

`make style` applies formatting fixes. Review its diff. `make spdx-check` verifies the exact pinned snapshot and generated legacy compatibility data; use `python scripts/update_spdx_licenses.py --help` for deliberate updates.

Keep regressions covered at the layer that owns the behavior. Preserve read-only checks, year-only repairs, all other bytes/mode, link/race refusal, JSON, exit codes, and Action outputs. Never infer legal ownership or licensing.

## Documentation

The five pages in `docs/` use [Zensical](https://zensical.org/), configured in
`zensical.toml`. Markdown, admonitions, code tabs, and theme settings should feel
familiar to Material for MkDocs users; this site uses Zensical's default modern
theme. The pinned `docs` dependency group is separate from runtime dependencies.
Previewing or building the site does not compile or install this Rust project:

```shell
make docs-serve  # http://localhost:8000
make docs       # strict production build in site/
```

Keep examples aligned with the CLI and distinguish the published 0.6.0 Python
release from multilingual features on `main`. Check links and preview each page
at desktop and mobile widths. Use the README for the maintained annual workflow
template rather than duplicating it across documentation pages.

### Hosting decision: GitHub Pages

Publish the generated static HTML at
`https://frgfm.github.io/lint-my-headers/`. GitHub Pages keeps documentation,
review, build artifacts, and deployment in the existing repository, with no
Cloudflare account, API token, or Worker code to maintain.

| Consideration | GitHub Pages | Cloudflare Workers static assets |
| --- | --- | --- |
| Performance | Static hosting is sufficient for this small documentation site. The theme uses system fonts and local assets. | Assets are distributed and cached across Cloudflare's network; offers more control over cache/response headers and routing. |
| Operations | Native GitHub Actions deployment and no additional deployment secret. | Requires a Cloudflare account and deployment setup; static-only assets do not require Worker code. |
| SEO and generative-engine discoverability | Serves the complete page HTML, titles, descriptions, canonical URLs, and sitemap. | Can serve the same HTML and metadata. Hosting provider alone gives no guaranteed ranking or citation advantage. |

There is no measured regional latency comparison for this project. Reconsider
Workers if actual traffic shows a latency problem or we need custom redirects,
response headers, or dynamic routes. See the providers' documentation for
[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages),
[Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits),
and [Workers static assets](https://developers.cloudflare.com/workers/static-assets/).

For indexing, keep the production `site_url` stable, verify the generated
`sitemap.xml`, link the site from the README, PyPI metadata, and the repository's
About website field, and submit the sitemap to the search-console services after
publication. The workflow does not change the repository's About field. These
steps aid discovery; indexing, ranking, and AI citations remain up to each service.
There is no special GEO markup required for these static documentation pages.
Avoid authentication or crawler challenges on public docs. If moving to
Cloudflare later, review its bot controls so intended search and AI retrieval
crawlers can still access the HTML. A project-site `docs/robots.txt` would live
below `/lint-my-headers/`, so it would not control origin-wide crawling.

### Deployment setup

After merge, select **Settings → Pages → Build and deployment → Source → GitHub
Actions** and run the `documentation` workflow on `main` if needed. The workflow
builds on pull requests and deploys only `main` pushes or a manual run on `main`.
It grants Pages write/OIDC permissions only to the deployment job. PR artifacts
are review downloads, not publicly indexed preview sites. This PR does not enable
Pages or publish the site by itself.

If adopting a custom domain, update `site_url` and the links to the production
site together, configure the domain in Pages settings, and preserve redirects
from the old public URLs.

Report reproducible problems through [issues](https://github.com/frgfm/lint-my-headers/issues). Pull requests should describe changed behavior, checks run, and unverified platform/release gates. Publication and repository mutations follow the owner-controlled checklist in [RELEASE_NOTES.md](RELEASE_NOTES.md).
