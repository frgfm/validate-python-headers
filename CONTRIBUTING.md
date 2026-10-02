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
familiar to Material for MkDocs users. The site uses Zensical's default `modern`
variant, including its colors, layout, controls, and components. The only custom
CSS changes font families: `docs/stylesheets/fonts.css` applies Manrope to
headings, IBM Plex Sans to body text, and IBM Plex Mono to code. Keep that style
sheet limited to font definitions and families. Fonts are self-hosted in
`docs/assets/fonts/`; source versions and original OFL notices are included
there. `docs/assets/images/logo.svg` is the project's header monogram: two
comment slashes joined into an H beneath a header bar, drawn in warm copper
(`#BA5B3B`). Its two filled shapes read at small sizes and use the same color in
both themes. Zensical uses the same SVG for the header logo and favicon; keep it
simple enough to read at 16 pixels. Dark mode is the initial setting regardless of the
system preference; the native theme toggle switches to light and remembers the
visitor's choice.
The pinned `docs` dependency group is separate from runtime dependencies.
Previewing or building the site does not compile or install this Rust project:

```shell
make docs-serve  # http://localhost:8000
make docs       # strict production build in site/
make docs-cloudflare  # build and stage .docs-site/lint-my-headers/
```

Keep examples aligned with the CLI and distinguish the published 0.6.0 Python
release from multilingual features on `main`. Check links and preview each page
at desktop and mobile widths. Use the README for the maintained annual workflow
template rather than duplicating it across documentation pages.

Keep review screenshots outside Git history. Upload captures through the GitHub
pull request editor and embed the returned GitHub asset URLs in the PR description.
`.github/docs-preview/` is ignored for local captures; the site's logo and font
assets remain normal versioned project files.

### Hosting decision: Cloudflare Workers static assets

Publish the generated static HTML at
`https://docs.fgfm.dev/lint-my-headers/`. Cloudflare Workers static assets is a
good fit for a shared documentation domain: `wrangler.toml` keeps the domain,
asset routing, and deployment configuration in the repository. Assets are served
directly without JavaScript Worker code.

| Consideration | GitHub Pages | Cloudflare Workers static assets |
| --- | --- | --- |
| Performance | Static hosting is sufficient for this small documentation site. Font files total about 85 KB and all assets are served locally. | Assets are distributed and cached across Cloudflare's network; offers more control over cache/response headers and routing. |
| Operations | Native GitHub Actions deployment and no additional deployment secret. A custom domain belongs to a user/organization site or an individual repository site. | Requires Cloudflare deployment credentials; Custom Domains handle DNS and TLS, and Workers Routes can direct future project paths to separate deployments. |
| SEO and generative-engine discoverability | Serves the complete page HTML, titles, descriptions, canonical URLs, and sitemap. | Can serve the same HTML and metadata. Hosting provider alone gives no guaranteed ranking or citation advantage. |

There is no measured regional latency comparison for this project. Both hosts
are suitable for this small static site; the shared custom domain and versioned
routing configuration favor Workers here. See the providers' documentation for
[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages),
[Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits),
and [Workers static assets](https://developers.cloudflare.com/workers/static-assets/).

For indexing, keep the production `site_url` stable, verify the generated
`sitemap.xml`, link the site from the README, PyPI metadata, and the repository's
About website field, and submit the sitemap to the search-console services after
publication. The workflow does not change the repository's About field. These
steps aid discovery; indexing, ranking, and AI citations remain up to each service.
There is no special GEO markup required for these static documentation pages.
Avoid authentication or crawler challenges on public docs. Configure Cloudflare's
bot controls so intended search and AI retrieval crawlers can access the HTML.
A project-site `docs/robots.txt` would live
below `/lint-my-headers/`, so it would not control origin-wide crawling.

### Deployment setup

The `documentation` workflow builds and validates Wrangler without credentials
on pull requests. It uploads the prefixed asset bundle and deploys that exact
bundle only on `main` pushes or a manual run on `main`. GitHub permissions remain
read-only. The deployment job uses the `docs-production` environment.

Before the first deployment:

1. Ensure `fgfm.dev` is an active zone in the intended Cloudflare account and
   `docs.fgfm.dev` is available for this Worker Custom Domain.
2. Configure the `docs-production` GitHub environment with
   `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`. Use the
   [Edit Cloudflare Workers API token template](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/),
   scoped to the intended account and zone.
3. Merge and run the `documentation` workflow on `main` if needed. Wrangler
   provisions the Custom Domain's DNS and TLS during deployment.

The Custom Domain covers the whole `docs.fgfm.dev` hostname; this first project
serves assets only below `/lint-my-headers/`. Future projects can use more-specific
[Workers Routes](https://developers.cloudflare.com/workers/configuration/routing/routes/),
which take precedence over the
[Custom Domain](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/).
Coordinate hostname-level settings when adding projects. Wrangler disables
`workers.dev` and version-preview URLs to keep a single public canonical origin.

For local Cloudflare routing checks after `make docs-cloudflare`, use Node 22+
and the Wrangler version pinned in the workflow:

```shell
npx --yes wrangler@4.147.0 deploy --dry-run
npx --yes wrangler@4.147.0 dev --local
# http://localhost:8787/lint-my-headers/
```

PR artifacts are review downloads. Preparing this configuration does not create
Cloudflare resources or publish the production site.

Report reproducible problems through [issues](https://github.com/frgfm/lint-my-headers/issues). Pull requests should describe changed behavior, checks run, and unverified platform/release gates. Publication and repository mutations follow the owner-controlled checklist in [RELEASE_NOTES.md](RELEASE_NOTES.md).
