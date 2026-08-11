# divi-migrator

> **WordPress Avada / Plain HTML → Divi 5 migration framework** (Elementor planned, not yet implemented).
> Built for AI-assisted workflows, zero vendor lock-in.

[![PyPI](https://img.shields.io/pypi/v/divi-migrator)](https://pypi.org/project/divi-migrator/)
[![Python](https://img.shields.io/pypi/pyversions/divi-migrator)](https://pypi.org/project/divi-migrator/)
[![License](https://img.shields.io/github/license/chriscstewart/Divi-Migrator)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/chriscstewart/Divi-Migrator/test.yml)](https://github.com/chriscstewart/Divi-Migrator/actions)

> ⚠️ **STATUS: EXPERIMENTAL / PRE-RELEASE.** This project is shared as-is for
> developers and AI agents working on Divi migrations. It is **not** a
> turnkey, certified product. Read [Known Limitations](#-known-limitations)
> and [Disclaimer](#-disclaimer--no-warranty) before use.
>
> 🛑 **ALWAYS run against a staging copy first. Never on production.** The
> tool rewrites and renames content; mistakes are your responsibility to
> recover from (rollback helpers exist, but are not guaranteed).

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **Auto-discovery** | Finds all pages/posts with builder content via WP REST API |
| 🎯 **Format detection** | Auto-detects Avada or plain HTML (Elementor detection reserved for a future release) |
| 🎨 **Design system** | Fetches global colors, fonts, presets from Divi Customizer |
| 🔒 **Safe replacement** | Existing content renamed to `-old`, moved to Draft (not deleted) |
| 🏷️ **Migration tracking** | All migrated content tagged with `divi-migrator` category |
| 🔄 **Resumable** | JSON checkpoint survives crashes/restarts |
| 🧹 **Deduplication** | Keeps newest draft per source, removes rest |
| ✅ **Verification** | Validates sections, rows, modules, images, buttons, colors |
| ⚡ **Rate limiting** | Configurable, respects security plugins |
| 🔌 **Extensible** | Plugin architecture for new builders |


---

## 🚀 Quick Start

```bash
# Install
pip install divi-migrator

# Configure (env vars or config.yaml)
export WP_URL="https://yoursite.com"
export WP_USER="migration-bot"
export WP_APP_PASSWORD="***"

# 1. Record current originals (pages/posts) so they can be tracked/rolled back.
#    Safe to re-run; migrate also auto-inits this on first use.
divi-migrate audit-init

# 2. Discover what can be migrated (lists only audit-recorded originals)
divi-migrate discover --type page
divi-migrate discover --type post

# 3. Dry run FIRST (migrate is dry-run by default — nothing is written)
divi-migrate migrate --type post --limit 5 --dry-run
divi-migrate migrate --type page --limit 50 --dry-run

# 4. Real migration — you MUST pass --execute to actually write
divi-migrate migrate --type page --limit 50 --execute
divi-migrate migrate --type post --limit 100 --execute

# 5. Cleanup duplicates (keeps newest draft per source)
divi-migrate cleanup --type post

# Inspect target site's design system
divi-migrate inspect
```

> ⚠️ `migrate` is **dry-run by default**. It only writes to the site when you
> pass `--execute`. Always do a `--dry-run` on staging and review before
> executing.

---

## 📋 Migration Process

Before running the migration, follow these steps to prepare your target site:

> 📌 **Command order matters.** Before `discover`/`migrate` can find anything,
> the originals must be recorded via `divi-migrate audit-init` (or the first
> `migrate` auto-inits it). See [Quick Start](#-quick-start) for the exact
> command sequence. Everything below prepares the *site*; the CLI commands do
> the migration.

### 1. Create a Staging Website First
Never run migrations directly on production. Create a complete staging copy of your site.

### 2. Install and Activate the Latest Divi 5 Theme
Ensure the target site runs Divi 5 (not Divi 4).

### 3. Create a New Blank Homepage and Configure Design Foundation
- Create a new homepage using **Divi5**
- Configure **Divi Options**
- Configure **Divi Customizer settings** 
- Set up **global styling/design system** (colors, fonts, spacing, button defaults, site background, section backgrounds - that will be reused on other pages)

**Confirm the new design foundation is correct before migration.** This is what all migrated content will use.

### 4. Create a Dedicated WordPress Migration User
- Create a separate account only for migration tasks
- Generate an **Application Password** for this user
- This isolates migration activity and simplifies rollback/auditing

### 5. Install and Activate the DiviOps Plugin
The [DiviOps plugin](https://github.com/oaris-dev/diviops) provides the REST API endpoints required for migration.

### 6. Connect Your AI Agent (optional)

This framework talks to WordPress **directly via the WP REST API** (using an
Application Password) — no WordPress MCP server is required. The optional
[DiviOps plugin](https://github.com/oaris-dev/diviops) supplies additional
Divi 5 REST endpoints used for best-effort block enrichment. An AI agent using
this tool only needs network access to those REST endpoints; it does not need
to drive a separate MCP server.

### 7. Give the AI Agent Migration Instructions
Example prompt:
> "Migrate this website from [source theme] to Divi 5 using Divi-Migrator: https://github.com/chriscstewart/Divi-Migrator/."

The tool automatically tags/categorizes migrated content with `divi-migrator` so it can be easily reviewed, filtered, updated, or removed.

---

## 🏗️ Requirements

| Component | Version |
|-----------|---------|
| WordPress | 6.0+ |
| Divi | 5.0+ |
| [**DiviOps Plugin**](https://github.com/oaris-dev/diviops) | Active (provides REST endpoints for Divi5) |
| Auth | Application Password (WP 5.6+) |

### DiviOps Endpoints Required

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/wp-json/diviops/v1/page/create` | POST | Create draft with Divi content |
| `/wp-json/diviops/v1/page/update-content/{id}` | POST | Push Divi 5 blocks |
| `/wp-json/diviops/v1/page/get/{id}` | GET | Read page data |
| `/wp-json/diviops/v1/page/get-layout/{id}` | GET | Verify block tree |
| `/wp-json/diviops/v1/meta/flush-cache` | POST | Clear Divi cache |
| `/wp-json/diviops/v1/validate/blocks` | POST | Validate block structure |
| `/wp-json/diviops/v1/global-color/list` | GET | Fetch global colors |
| `/wp-json/diviops/v1/global-font/list` | GET | Fetch global fonts |
| `/wp-json/diviops/v1/preset/list` | GET | Fetch module presets |

---

## ⚙️ Configuration

### Environment Variables

```bash
# Required
WP_URL=https://yoursite.com
WP_USER=migration-bot
WP_APP_PASSWORD=***

# Optional
DIVIOPS_URL=https://yoursite.com          # if different from WP_URL
RATE_LIMIT=0.33                            # requests/sec for WP+DiviOps (0.33 ≈ 3s apart)
CHECKPOINT_DIR=./checkpoints
SSL_VERIFY=true
```

### Config File (`config.yaml`)

```yaml
wp:
  url: "https://yoursite.com"
  user: "migration-bot"
  app_password: "${WP_APP_PASSWORD}"
  ssl_verify: true
  timeout: 30

diviops:
  url: "https://yoursite.com"   # same as WP_URL if on same host

migration:
  rate_limit: 0.33          # requests/sec for WP+DiviOps (0.33 ≈ 3s apart; raise cautiously)
  batch_size: 50
  checkpoint_dir: "./checkpoints"
  max_retries: 5            # retry attempts on transient 5xx/429
  timeout: 30

verification:
  require_sections: true
  require_images: false
  require_buttons: false
  primary_color_token: "gcid-primary-color"
  default_section_bg: "#f7f4ef"

design_system:
  fetch_on_start: true
  cache_ttl: 3600
  fallback_to_defaults: true
  primary_color_override: null
  section_bg_override: null
```

---

## 🔌 Extending for New Builders

Converters subclass `BaseConverter` and register an instance in the module-level
`registry`. The active converter is chosen automatically by `detect()`.

```python
# my_converters/custom.py
from divi_migrator.converters.base import BaseConverter, ExtractedAssets
from divi_migrator.converters.base import registry


class CustomBuilderConverter(BaseConverter):
    format_name = "custom_builder"

    def detect(self, content: str) -> bool:
        return "custom_builder_shortcode" in content

    def convert(
        self,
        content: str,
        source_id: int,
        design_system: object = None,
        wp_client: object = None,
    ) -> str:
        # Transform to Divi 5 block markup (see divi5_blocks helpers)
        return divi5_markup

    def extract_assets(self, content: str) -> ExtractedAssets:
        return ExtractedAssets()


# Register so discovery/migration can auto-select it
registry.register("custom_builder", CustomBuilderConverter)
```

There is **no `--converter` CLI flag** — `divi-migrate discover`/`migrate`
auto-detect the format per item and pick the matching registered converter.
To use your custom converter, ensure the module is imported (so `registry.register`
runs) before invoking the CLI, e.g. via an entry point or by importing it in your
own script that calls the library.

---

## 📁 Project Structure

```
divi_migrator/
├── cli.py              # Typer CLI entrypoint
├── config.py           # Pydantic Settings (env + YAML)
├── core/
│   ├── client.py       # WP REST + DiviOps clients
│   ├── inspector.py    # Design system fetcher
│   ├── discovery.py    # Content discovery
│   ├── orchestrator.py # Migration pipeline
│   ├── checkpoint.py   # JSON checkpoint I/O
│   └── verification.py # Layout verification
├── converters/
│   ├── base.py         # BaseConverter + Registry
│   ├── avada.py        # Fusion Builder → Divi 5
│   ├── elementor.py    # Elementor (stub — not implemented in this release)
│   └── plain_html.py   # HTML → Divi 5 wrapper
├── models/
│   ├── __init__.py     # MigrationMeta, CheckpointRecord, etc.
│   └── design_system.py # DesignSystem, GlobalColors, etc.
```

---

## 🧪 Testing

```bash
# Unit tests (no external services required)
pytest tests/unit/ -v

# Lint + type check (must match CI)
ruff check .
ruff format --check .
mypy --strict divi_migrator
```

> Integration tests against a live WordPress + DiviOps site are **not included**
> in this release. CI runs the unit suite, ruff, and strict mypy only.

---

## 🔐 Security

- No credentials stored in code — uses environment variables
- Authentication details never logged
- SSL verification enabled by default (warns if disabled)
- URL validation before requests
- Unsafe protocols rejected

---

## ⚠️ Known Limitations

### Section / Row / Module Backgrounds (DiviOps rendering)

The migrator emits **correct, schema-valid Divi 5 background markup** (e.g.
`background.color.desktop.value = "#770000"` or
`background.image.desktop.value = {src, url}`) when the source has a
background, and **omits** the `background` key entirely when it does not
(matches real Divi 5).

However, **DiviOps's headless API does not apply section/row backgrounds at
render time** (verified 2026-08-08):

- `page/create` / posts `update-content` **drop** `module.decoration` entirely.
- `module_update` **stores** the attribute (visible via `module_get`,
  `attr_count` increases) but the published page / `render_preview` emit **no
  `background-color` CSS**.

This is a platform limitation of DiviOps on this host, not a code defect.
The correct markup is preserved so backgrounds become editable in the Divi
Visual Builder or self-heal if DiviOps ever renders them. If you need
backgrounds applied immediately, set them manually per section/row in the
Divi editor after migration.

### Post & Page Creation Bypass DiviOps (by design)

Both posts and pages are **created via the WordPress REST endpoints**
(`posts` / `pages`), not DiviOps:

- `create_content` calls `self.wp.post("posts"|"pages", ...)` to create the
  draft (correct post-type, block markup stored in `post_content`). Divi 5
  renders block markup directly from `post_content`, so this is the reliable
  creation path.
- DiviOps `update_page_content` is attempted as a **best-effort enrichment**
  only (it may 500 on large payloads on shared hosting) and is **not required**
  for rendering.

Pages previously used DiviOps `page/create`, but that endpoint 500s on large
payloads (shared hosting), leaving pages as empty placeholders. Routing page
creation through WP REST fixed that. (See `core/client.py::create_content`.)

---

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

## 🛡️ Disclaimer / No Warranty

This software is provided **"AS IS" and "AS AVAILABLE"**, without warranty of
any kind, express or implied, including but not limited to the warranties of
merchantability, fitness for a particular purpose, and non-infringement.

**The authors and contributors take NO RESPONSIBILITY and assume NO LIABILITY**
for any damage, data loss, broken layouts, SEO regression, or any other
consequence arising from the use of this tool. This includes, without limitation:

- Content that is **renamed, rewritten, unpublished, or left in a draft** state.
- **Lost styling, backgrounds, or module fidelity** after migration (see
  [Known Limitations](#-known-limitations)).
- Failures due to hosting limits, plugin conflicts, rate limiting, or DiviOps
  behaviour on your specific site.
- Any outcome of running the tool on a site that is not a disposable staging copy.

**You are solely responsible** for:

1. **Backing up your site** (database + uploads) before running anything.
2. **Testing on staging first**, verifying the result, and only then
   considering production.
3. Reviewing migrated content in the Divi Visual Builder before publishing.

By using this software you acknowledge and accept these terms. If you do not
agree, do not use the software.
