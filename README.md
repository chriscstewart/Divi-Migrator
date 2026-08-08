# divi-migrator

> **WordPress Avada/Elementor/Plain HTML → Divi 5 migration framework.**
> Built for AI-assisted workflows, zero vendor lock-in.

[![PyPI](https://img.shields.io/pypi/v/divi-migrator)](https://pypi.org/project/divi-migrator/)
[![Python](https://img.shields.io/pypi/pyversions/divi-migrator)](https://pypi.org/project/divi-migrator/)
[![License](https://img.shields.io/github/license/chriscstewart/Divi-Migrator)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/chriscstewart/Divi-Migrator/test.yml)](https://github.com/chriscstewart/Divi-Migrator/actions)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **Auto-discovery** | Finds all pages/posts with builder content via WP REST API |
| 🎯 **Format detection** | Auto-detects Avada, Elementor, or plain HTML |
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

# Discover what can be migrated
divi-migrate discover --type page
divi-migrate discover --type post

# Dry run
divi-migrate migrate --type post --limit 5 --dry-run

# Real migration (resumable!)
divi-migrate migrate --type page --limit 50
divi-migrate migrate --type post --limit 100

# Cleanup duplicates
divi-migrate cleanup --type post

# Inspect target site's design system
divi-migrate inspect
```

---

## 📋 Migration Process

Before running the migration, follow these steps to prepare your target site:

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

### 6. Connect Your AI Agent to Required MCP Tools
- **DiviOps MCP** — required for all Divi 5 operations
- [**WordPress MCP**](https://github.com/docdyhr/mcp-wordpress) — for additional WP operations: WordPress REST API endpoints used by default, but some agents may prefer this MCP. 

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
RATE_LIMIT=2.0                            # seconds between requests
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
  rate_limit: 2.0
  batch_size: 50
  checkpoint_dir: "./checkpoints"
  max_retries: 3
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

```python
# my_converters/custom.py
from divi_migrator.converters import BaseConverter, register_converter

class CustomBuilderConverter(BaseConverter):
    format_name = "custom_builder"

    def detect(self, content: str) -> bool:
        return 'custom_builder_shortcode' in content

    def convert(self, content: str, source_id: int, design_system=None) -> str:
        # Transform to Divi 5 shortcodes
        return divi_shortcodes

    def extract_assets(self, content: str) -> ExtractedAssets:
        return ExtractedAssets()

# Register
from divi_migrator.converters import register_converter
register_converter("custom_builder", CustomBuilderConverter)
```

Then use: `divi-migrate migrate --converter custom_builder`

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
│   ├── elementor.py    # Elementor → Divi 5 (stub)
│   └── plain_html.py   # HTML → Divi 5 wrapper
├── models/
│   ├── __init__.py     # MigrationMeta, CheckpointRecord, etc.
│   └── design_system.py # DesignSystem, GlobalColors, etc.
```

---

## 🧪 Testing

```bash
# Unit tests
pytest tests/unit/ -v

# Integration (requires test WP site)
pytest tests/integration/ --wp-url=https://test.site --wp-user=... --wp-pass=...

# Lint + type check
ruff check .
mypy divi_migrator/
```

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

---

## 📄 License

MIT License - see [LICENSE](LICENSE)
