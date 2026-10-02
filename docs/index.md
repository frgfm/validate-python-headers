---
description: A Rust CLI for checking source copyright and license headers and safely refreshing recognized stale years.
hide:
  - navigation
  - toc
---

<section class="lmh-hero" aria-labelledby="lint-my-headers">
  <div class="lmh-hero__copy">
    <span class="lmh-eyebrow">Copyright &amp; license header checks</span>
    <h1 id="lint-my-headers">Lint My Headers</h1>
    <p class="lmh-hero__lead">Consistent headers.<br>Conservative repairs.</p>
    <p>Check source headers across nine languages. Declare your policy, find issues, and refresh recognized stale years while preserving everything else.</p>
    <p class="lmh-hero__actions"><a href="getting-started/" class="md-button md-button--primary">Get started</a><a href="https://github.com/frgfm/lint-my-headers" class="md-button">View on GitHub</a></p>
  </div>
  <figure class="lmh-example" aria-label="A recognized year repair preserves the creation year and owner">
    <figcaption><span>One year. One small diff.</span><code>src/example.py</code></figcaption>
    <div class="lmh-example__body">
      <div class="lmh-example__label">Before · <code>LMH004</code></div>
      <pre><code># Copyright (C) 2024-<span class="lmh-year--before">2025</span>, Example Organization.</code></pre>
      <div class="lmh-example__command"><span aria-hidden="true">$</span> <code>lmh fix</code></div>
      <div class="lmh-example__label">After · a recognized repair in 2026</div>
      <pre><code># Copyright (C) 2024-<span class="lmh-year--after">2026</span>, Example Organization.</code></pre>
      <p>The creation year, owner, and every other byte stay intact.</p>
    </div>
  </figure>
</section>

<div class="lmh-facts">
  <div><p><strong>Nine languages</strong></p><p>Python, JavaScript, TypeScript, Rust, Go, Swift, Bash, C, and C++ in the source CLI.</p></div>
  <div><p><strong>Read-only checks</strong></p><p><code>lmh check</code> reports what needs attention without writing source files.</p></div>
  <div><p><strong>Year-only repairs</strong></p><p><code>lmh fix</code> updates one recognized stale year for your configured owner.</p></div>
</div>

## From policy to pull request

<div class="lmh-workflow">
  <div><span class="lmh-step">1</span><h3>Declare your policy</h3><p>Set the owner, earliest creation year, license notice, and source paths.</p></div>
  <div><span class="lmh-step">2</span><h3>Run a check</h3><p>Use <code>lmh check</code> locally, in CI, or from a coding agent. Review each finding.</p></div>
  <div><span class="lmh-step">3</span><h3>Review the diff</h3><p>Run <code>lmh fix</code> for eligible stale years, recheck, and inspect the changes.</p></div>
</div>

## Choose your next step

<div class="lmh-guides">
  <a href="getting-started/" class="lmh-guide">
    <span class="lmh-guide__title"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24"><path d="M12 19h8M4 17l6-6-6-6"/></svg><strong>Getting started</strong><span aria-hidden="true"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14m-6-6 6 6-6 6"/></svg></span></span>
    <span class="lmh-guide__description">Install the CLI, declare a first policy, and check your existing headers.</span>
  </a>
  <a href="configuration/" class="lmh-guide">
    <span class="lmh-guide__title"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24"><path d="M14 17H5M19 7h-9"/><circle cx="17" cy="17" r="3"/><circle cx="7" cy="7" r="3"/></svg><strong>Configuration</strong><span aria-hidden="true"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14m-6-6 6 6-6 6"/></svg></span></span>
    <span class="lmh-guide__description">Find the right configuration file, language selectors, and header layouts.</span>
  </a>
  <a href="integrations/" class="lmh-guide">
    <span class="lmh-guide__title"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7M6 9v12"/></svg><strong>Integrations</strong><span aria-hidden="true"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14m-6-6 6 6-6 6"/></svg></span></span>
    <span class="lmh-guide__description">Add pre-commit, prek, the GitHub Action, or an annual review workflow.</span>
  </a>
  <a href="diagnostics/" class="lmh-guide">
    <span class="lmh-guide__title"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2M20 14h2M15 13v2M9 13v2"/></svg><strong>Diagnostics &amp; agents</strong><span aria-hidden="true"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12h14m-6-6 6 6-6 6"/></svg></span></span>
    <span class="lmh-guide__description">Interpret findings, consume JSON, and give coding agents an explicit contract.</span>
  </a>
</div>

## Repair boundaries

Repairs preserve the creation year, body bytes, and file mode. Ambiguous layouts,
unsafe links, and concurrently changed targets are refused. Missing headers,
wrong owners, malformed notices, and future years require manual review.

Ownership and licensing always come from your declared policy. Lint My Headers
does not insert missing headers or establish legal, SPDX, or REUSE compliance.
Both `lmh` and `lint-my-headers` expose the same commands, with no language
toolchain or Node.js runtime needed by the installed native CLI.

The project is licensed under
[Apache-2.0](https://github.com/frgfm/lint-my-headers/blob/main/LICENSE).
[Report an issue](https://github.com/frgfm/lint-my-headers/issues) or read the
[contributor guide](https://github.com/frgfm/lint-my-headers/blob/main/CONTRIBUTING.md).
