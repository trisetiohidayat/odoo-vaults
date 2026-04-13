---
type: module
name: http_routing
version: Odoo 18
tags: [module, http_routing, seo, slug, multilang, routing]
source: ~/odoo/odoo18/odoo/addons/http_routing/
---

# http_routing

Multilingual SEO-friendly URL routing, slug generation, language handling, and URL rewriting for the Odoo website/frontend.

**Source:** `addons/http_routing/`
**Depends:** `base`

---

## Models

### `ir.http` Extension — URL Routing Core

```python
class IrHttp(models.AbstractModel):
    _inherit = ['ir.http']
```

#### Class Constants

```python
_UNSLUG_RE = re.compile(r'(?:(\w{1,2}|\w[A-Za-z0-9-_]+?\w)-)?(-?\d+)(?=$|\/|#|\?)')
```

#### Slug Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `_slug(value)` | `str` | Converts record to slugged URL: `"name-123"`. Returns just ID if no name. |
| `_unslug(value)` | `tuple` | Extracts `(slug, id)` from URL string. Returns `(None, None)` if no match. |
| `_unslug_url(value)` | `str` | Converts `/blog/my-super-blog-1` → `/blog/1` |

#### URL Methods

| Method | Description |
|--------|-------------|
| `_url_localized(url, lang_code, canonical_domain, prefetch_langs, force_default_lang)` | Returns URL with lang suffix + translated slugs |
| `_url_lang(path_or_uri, lang_code)` | Adds/removes language prefix from URL |
| `_url_for(url_from, lang_code)` | Applies URL rewriting for language |
| `_is_multilang_url(local_url, lang_url_codes)` | Checks if URL should be translated |
| `_get_default_lang()` | Returns default language from `ir.default` or first active lang |
| `get_nearest_lang(lang_code)` | Finds similar lang (e.g., `fr_BE` → `fr`) |
| `url_rewrite(path, query_args)` | Rewrites URLs with slugification. **ORM cached** for performance |

#### Multilang Matching (`_match()`) — 9-Step Algorithm

```
1. URL matches non-multilang endpoint → use URL as-is
2. No lang in URL, default lang requested → continue
3. Missing lang, bot user-agent → continue
4. No lang, POST request → continue
5. Missing lang → redirect /home → /fr/home  (301)
6. Default lang in URL → redirect /en/home → /home  (301)
7. Lang alias → redirect /fr_FR/home → /fr/home  (301)
8. Homepage with trailing slash → redirect /fr_BE/ → /fr_BE
9. Valid lang in URL → rewrite URL and continue
```

#### Dispatch / Error Handling

| Method | Description |
|--------|-------------|
| `_match(path)` | 9-step multilingual routing matcher |
| `_pre_dispatch(rule, args)` | Frontend dispatch with slug redirects (301) for SEO |
| `_frontend_pre_dispatch()` | Updates context with language, sets `frontend_lang` cookie |
| `_get_exception_code_values(exc)` | Maps exceptions → HTTP codes (403, 400, 500) |
| `_get_values_500_error(env, values, exc)` | Sets up 500 error rendering values |
| `_get_error_html(env, code, values)` | Renders error template `http_routing.<code>` |
| `_handle_error(exception)` | Serves frontend error pages (404, 403, 500) |

---

### `ir.qweb` Extension — Template Context

```python
class IrQweb(models.AbstractModel):
    _inherit = "ir.qweb"
```

| Method | Description |
|--------|-------------|
| `_prepare_environment(values)` | Adds `slug` and `unslug_url` to template context |
| `_prepare_frontend_environment(values)` | Adds `url_for` and `url_localized` to template context |

**Template context variables added:**
- `slug` → `ir.http._slug`
- `unslug_url` → `ir.http._unslug_url`
- `url_for` → `ir.http._url_for`
- `url_localized` → `ir.http._url_localized`

---

### `res.lang` Extension

```python
class ResLang(models.Model):
    _inherit = "res.lang"
```

| Method | Description |
|--------|-------------|
| `_get_frontend()` | Returns `LangDataDict` of available frontend languages by code |

---

## Controllers

### `main.py`

```python
class Routing(Home)
class SessionWebsite(Session)
```

| Route | Class | Auth | Description |
|-------|-------|------|-------------|
| `/website/translations/<unique>` | `Routing` | `public` | Website-specific `.po` translations |
| `/web/session/logout` | `SessionWebsite` | — | Website-aware logout with redirect |

---

## SEO Slug Format

```
# Pattern: (?:(?:\w{1,2}|\w[A-Za-z0-9-_]+?\w)-)?(-?\d+)
# Examples:
#   "Acme Corp-42"  → slug="Acme Corp", id=42
#   "42"            → slug=None, id=42
#   "-7"            → slug=None, id=-7  (negative IDs supported)
```

**Slug rules:**
- Spaces → hyphens
- Non-alphanumeric stripped (except hyphens)
- Leading/trailing hyphens stripped
- **Two-letter slugs reserved** for language codes (en, fr, de...)

---

## Error Pages

| HTTP Code | Template | Description |
|-----------|---------|-------------|
| 403 | `http_routing.403` | Forbidden |
| 404 | `http_routing.404` | Not Found |
| 500 | `http_routing.500` | Internal Error |

---

## Cross-Module Relations

| Module | Integration |
|--------|-------------|
| `website` | Depends on http_routing for all frontend routing |
| `web` | Session + translation bootstrap |
| `web` | `get_frontend_session_info` extends parent |
| `base` | `ir.http` base class, `res.lang` extension |

---

## Edge Cases

| Scenario | Behavior |
|----------|---------|
| Negative IDs | Uses `abs()` if slug not found |
| Bot UA missing lang | Continues without redirect |
| POST without lang | No redirect (preserves form data) |
| Slug conflicts | Two records with same name → different IDs in slug |
| `fr_FR` URL | Redirects to canonical `/fr/home` |
| `url_rewrite` cache | `ormcache` — invalidates on registry rebuild |

---

## Related Links
- [Core/HTTP Controller](odoo-18/Core/HTTP Controller.md) — HTTP routing reference
- [Modules/web](Modules/web.md) — Web client session management
- [Modules/website](Modules/website.md) — Website builder
