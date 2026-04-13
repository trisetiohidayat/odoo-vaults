---
type: module
module: http_routing
tags: [odoo, odoo19, http, routing, seo, url, multilingual, website]
created: 2026-04-11
---

# http_routing Module

**Category:** Hidden
**Depends:** `web`
**Sequence:** 9100 (loaded late — after most modules, especially `website` and `portal`)
**Author:** Odoo S.A.
**License:** LGPL-3
**Source:** `odoo/addons/http_routing/`

## Overview

The `http_routing` module provides **advanced web routing** for Odoo, specifically focused on **multilingual URL management**, **SEO-friendly slug generation**, and **frontend error page rendering**. It extends the base `ir.http` (in `odoo/addons/base`) with language detection, URL rewriting, canonical URL handling, and custom HTTP error pages.

This module is the backbone of Odoo's SEO infrastructure. It handles `/fr/...` language prefixes, 301 redirects from bare IDs to slugs, language alias resolution (`fr_FR` -> `fr`), trailing-slash cleanup, and renders custom HTML error pages (400, 403, 404, 415, 422, 500). It also wires QWeb templates to receive slug utilities (`slug`, `unslug_url`, `url_for`, `url_localized`).

## Module Structure

```
http_routing/
├── __init__.py                    # post_init_hook: sets request.is_frontend=False during init
├── __manifest__.py                # depends: web, sequence: 9100, post_init_hook
├── models/
│   ├── __init__.py
│   ├── ir_http.py                # Main routing: slug, multilang, redirects, error handling (630 lines)
│   ├── ir_qweb.py                # QWeb extension: injects slug/url_for/url_localized into templates
│   └── res_lang.py               # Adds _get_frontend() to res.lang
├── controllers/
│   ├── __init__.py
│   └── main.py                   # /website/translations endpoint; logout override
├── views/
│   ├── http_routing_template.xml # Error page templates (400, 403, 404, 415, 422, 500)
│   └── res_lang_views.xml        # Adds url_code field to res.lang form/tree views
├── static/src/scss/http_routing.scss
└── tests/
    ├── __init__.py
    ├── common.py
    ├── test_res_lang.py
    └── (test files for routing/slug behavior)
```

### `__init__.py` — Post-Init Hook

```python
def _post_init_hook(env):
    if request:
        request.is_frontend = False
        request.is_frontend_multilang = False
```

Used during module installation to prevent premature frontend detection before routing is initialized.

---

## Architecture: Method Resolution Order

`http_routing` extends `ir.http` in this chain:

```
ir.http (odoo/addons/base)                          # Base: _slug, _unslug, _match, _get_converters
  └── web (ir_http override)                         # Adds: is_a_bot, _handle_debug, session_info
        └── http_routing (ir_http override)          # Adds: slug regex, multilang, redirects, canonical
              └── website (ir_http override)         # Full website routing with page serving
```

The `website` module further extends routing with `controllers.main.Website` and `models.ir_http.IrHttp`. The final `_match()` execution order:

1. `http_routing.ir_http._match()` — detects language, sets `request.lang`, handles redirects
2. `website.ir_http._match()` — falls through to Odoo base routing
3. Falls back to `base.ir_http._match()` for non-website endpoints

---

## Core Extension: `ir.http`

**File:** `models/ir_http.py`
**Inheritance:** `_inherit = 'ir.http'`
**Type:** `models.AbstractModel` (singleton-like mixin, no database table)
**Rerouting limit:** `rerouting_limit = 10` (inherited from base, prevents redirect loops)

### Class Attributes

| Attribute | Type | Value | Purpose |
|-----------|------|-------|---------|
| `rerouting_limit` | `int` | `10` | Maximum `request.reroute()` calls before giving up — prevents infinite loops |

---

## Constants & Regex

```python
_UNSLUG_RE = re.compile(r'(?:(\w{1,2}|\w[\w-]+?\w)-)?(-?\d+)(?=$|\/|#|\?)')
_UNSLUG_ROUTE_PATTERN = r'(?:(?:\w{1,2}|\w[\w-]+?\w)-)?(?:-?\d+)(?=$|\/|#|\?)'
```

### `_UNSLUG_RE` Breakdown

| Group | Pattern | Matches |
|-------|---------|---------|
| Optional prefix | `(?:\w{1,2}|\w[\w-]+?\w)` | Short codes (`fr`, `en`) OR word with internal hyphens (`my-post`, `hello-world`) |
| Optional dash before ID | `-?` | Single hyphen: `my-post-42`. Double-hyphen for negative IDs: `--42` |
| ID number | `-?\d+` | Positive or negative integer |
| End anchor | `(?=$|\/|#|\?)` | Stops at path separator, fragment, or query |

### Supported Slug Patterns

| URL segment | Captured slug | Captured ID | Notes |
|-------------|---------------|-------------|-------|
| `my-post-42` | `my-post` | `42` | Standard slug |
| `product-17` | `product` | `17` | No explicit slug |
| `fr` | (empty) | `fr` | 2-char code → matches as ID if no route found |
| `my-record--42` | `my-record` | `-42` | Double-dash = negative ID |
| `about-us-3` | `about-us` | `3` | Hyphenated slug |

### `_UNSLUG_ROUTE_PATTERN` — Werkzeug Route Matching

Used in `ModelConverter.regex` (line 35) so werkzeug routes like `/blog/<model("blog.post"):post>` can match `my-post-42`. The pattern does not capture groups — it just validates the full URL segment.

---

## Slug Utilities

### `_get_converters()` — Register Custom URL Converter

```python
@classmethod
def _get_converters(cls) -> dict[str, type]:
    return dict(
        super(IrHttp, cls)._get_converters(),
        model=ModelConverter,
    )
```

Overrides base's `{'model': ModelConverter, 'models': ModelsConverter, 'int': SignedIntConverter}` to replace `ModelConverter` with `http_routing`'s extended version. The `models` and `int` converters are inherited from base.

**L4 — Performance:** Called once per routing map build. The dict merge is O(1) since the super dict is already materialized.

---

### `_slug(value)` — Record → URL Segment

```python
@classmethod
def _slug(cls, value: models.BaseModel | tuple[int, str]) -> str:
    try:
        identifier, name = value.id, value.display_name
    except AttributeError:
        # assume name_search result tuple
        identifier, name = value
    if not identifier:
        raise ValueError("Cannot slug non-existent record %s" % value)
    slugname = cls._slugify(name or '')
    if not slugname:
        return str(identifier)
    return f"{slugname}-{identifier}"
```

**Type signature:** `value` is a `models.BaseModel` record OR a `(int, str)` tuple (result of `name_search`).

**L3 — Cross-model:** Uses `display_name` which triggers the record's name getter. For translatable models, `display_name` returns the name in the current `request.env.context['lang']` — this is the mechanism by which localized URLs are built.

**L3 — Failure modes:**
- `ValueError` raised if `identifier` is falsy (new record, id=0, or `None`)
- If `name` is empty/None/whitespace-only, `_slugify` returns empty string → falls back to bare ID
- Negative IDs: `_slugify(None)` is skipped, returns `-42` directly (no slug prefix)

**L4 — Performance:** `_slugify()` internally calls `python-slugify` library if available; falls back to manual regex processing. Slug is cached per record in Odoo's recordset cache, so repeated calls within same transaction are cheap.

**L4 — Odoo 18→19 change:** In Odoo 18, `_slug` used string formatting `%s` for `ValueError`. In 19, uses f-string interpolation. Behavior identical.

---

### `_unslug(value)` — URL Segment → `(slug, id)`

```python
@classmethod
def _unslug(cls, value: str) -> tuple[str | None, int] | tuple[None, None]:
    """ Extract slug and id from a string.
        Always return a 2-tuple (str|None, int|None)
    """
    m = _UNSLUG_RE.match(value)
    if not m:
        return None, None
    return m.group(1), int(m.group(2))
```

**Return type:** `tuple[str | None, int | None]`

**L3 — Edge case:** If the URL segment contains only digits (e.g., `42`), the optional prefix group captures nothing, returning `(None, 42)`. This means bare numeric IDs are handled correctly without requiring a slug.

**L4 — Regex backtracking:** The regex is written to avoid catastrophic backtracking on long strings. The outer group is non-capturing and alternation is ordered so the shorter pattern (`\w{1,2}`) is tried first.

---

### `_unslug_url(value)` — Full Path → Stripped Path

```python
@classmethod
def _unslug_url(cls, value: str) -> str:
    """ From /blog/my-super-blog-1" to "blog/1" """
    parts = value.split('/')
    if parts:
        unslug_val = cls._unslug(parts[-1])
        if unslug_val[1]:
            parts[-1] = str(unslug_val[1])
            return '/'.join(parts)
    return value
```

**L3 — Use case:** Converts SEO URLs to internal ID-based paths. Used in QWeb as `unslug_url` (see `ir_qweb.py`).

**L3 — Edge case:** Returns original URL unchanged if last segment doesn't match slug pattern (e.g., static assets, API endpoints).

---

## ModelConverter — Custom URL Converter

```python
class ModelConverter(ir_http.ModelConverter):

    def __init__(self, url_map, model=False, domain='[]'):
        super().__init__(url_map, model)
        self.domain = domain
        self.regex = _UNSLUG_ROUTE_PATTERN  # replaces base's r'[0-9]+'

    def to_python(self, value) -> models.BaseModel:
        record = super().to_python(value)
        if record.id < 0 and not record.browse(record.id).exists():
            # limited support for negative IDs due to our slug pattern, assume abs() if not found
            record = record.browse(abs(record.id))
        return record.with_context(_converter_value=value)
```

**L3 — Override of base:** Base `ModelConverter` uses `regex = r'[0-9]+'` and calls `browse(unslug(value)[1])` which strips the slug. This subclass replaces the regex to accept `my-post-42` instead of just `42`.

**L4 — Negative ID handling:** If `record.id < 0` and the record doesn't exist in DB, assumes the slug was `my-record--42` (double-dash encoding for negative IDs) and uses `abs(id)` as a fallback. This is a limited heuristic — it only works if the record with the positive ID exists.

**L4 — Context injection:** `with_context(_converter_value=value)` passes the original URL segment (e.g., `my-post-42`) to the controller via `request.params` or the record's context. Controllers can access this to do custom slug validation.

**L4 — Werkzeug integration:** `BaseConverter` is a werkzeug class. When Odoo builds routes via `router.build(args)`, the converter's `to_url(record)` is called (which calls `self.slug(record)` → `IrHttp._slug(record)`) to generate URLs from model objects.

---

## Language Tools

### `_get_default_lang()` — Resolve Default Language

```python
@classmethod
def _get_default_lang(cls) -> LangData:
    lang_code = request.env['ir.default'].sudo()._get('res.partner', 'lang')
    if lang_code:
        return request.env['res.lang']._get_data(code=lang_code)
    return next(iter(request.env['res.lang']._get_active_by('code').values()))
```

**Return type:** `LangData` (named tuple: `code`, `url_code`, `name`, `iso_code`, `active`)

**L3 — Priority chain:**
1. `ir.default` record for `res.partner.lang` field (user's preferred language setting)
2. First entry in `res.lang._get_active_by('code')` (first alphabetically active language)

**L4 — sudo():** Uses `sudo()` because `ir.default` lookup must work even for unauthenticated/public users who don't have read access to `ir.default` table.

**L4 — Odoo 18→19 change:** In Odoo 18, `_get_default_lang` returned the first language alphabetically by code. Odoo 19 added the `ir.default` check for partner lang, making it consistent with user preferences.

---

### `get_nearest_lang(lang_code)` — Fuzzy Language Matching

```python
@api.model
def get_nearest_lang(self, lang_code: str) -> str:
    """ Try to find a similar lang. Eg: fr_BE and fr_FR
        :param lang_code: the lang `code` (en_US)
    """
    if not lang_code:
        return None

    frontend_langs = self.env['res.lang']._get_frontend()
    if lang_code in frontend_langs:
        return lang_code

    short = lang_code.partition('_')[0]
    if not short:
        return None
    return next((code for code in frontend_langs if code.startswith(short)), None)
```

**L3 — Purpose:** Handles cases where URL contains `fr_BE` but only `fr_FR` is installed. Also used for `frontend_lang` cookie matching.

**L3 — Matching logic:**
1. Exact code match first (fast path)
2. Prefix match: `fr_BE` → `fr_FR` (finds first matching `fr_*`)
3. Falls back to `None` if no match

**L4 — Performance:** Uses generator with `next()` to avoid scanning all languages. `_get_frontend()` is cached via ORM.

---

### `_is_multilang_url(local_url, lang_url_codes)` — Check if URL is Translatable

```python
@classmethod
def _is_multilang_url(cls, local_url: str, lang_url_codes: list[str] | None = None) -> bool:
    ''' Check if the given URL content is supposed to be translated.
        To be considered as translatable, the URL should either:
        1. Match a POST (non-GET actually) controller that is `website=True` and
           either `multilang` specified to True or if not specified, with `type='http'`.
        2. If not matching 1., everything not under /static/ or /web/ will be translatable
    '''
    if not lang_url_codes:
        lang_url_codes = [lg.url_code for lg in request.env['res.lang']._get_frontend().values()]
    spath = local_url.split('/')
    # if a language is already in the path, remove it
    if spath[1] in lang_url_codes:
        spath.pop(1)
        local_url = '/'.join(spath)

    url = local_url.partition('#')[0].split('?')
    path = url[0]

    # Consider /static/ and /web/ files as non-multilang
    if '/static/' in path or path.startswith('/web/'):
        return False

    query_string = url[1] if len(url) > 1 else None

    # Try to match an endpoint in werkzeug's routing table
    try:
        _, func = request.env['ir.http'].url_rewrite(path, query_args=query_string)

        # /page/xxx has no endpoint/func but is multilang
        return (not func or (
            func.routing.get('website', False)
            and func.routing.get('multilang', func.routing['type'] == 'http')
        ))
    except Exception as exception:  # noqa: BLE001
        _logger.warning(exception)
        return False
```

**L3 — Decision logic:**
- Static assets (`/static/`) → never translatable
- Backend URLs (`/web/`) → never translatable
- Unknown paths (no endpoint) → assumed translatable (e.g., custom pages)
- Known endpoints: translatable only if `website=True` AND (`multilang=True` OR `type='http'`)

**L4 — Edge case:** A JSON controller (`type='json'`) with `website=True` is NOT multilingual by default — you must explicitly set `multilang=True`. This prevents JSON-RPC routes from being treated as translatable pages.

**L4 — Error suppression:** Catches all exceptions and returns `False` rather than propagating. This means URL rewriting silently skips malformed URLs rather than crashing.

---

### `_get_frontend()` — `res.lang` Extension

```python
# models/res_lang.py
class ResLang(models.Model):
    _inherit = "res.lang"

    def _get_frontend(self) -> LangDataDict:
        """ Return the available languages for current request
        :return: LangDataDict({code: LangData})
        """
        return self._get_active_by('code')
```

**L3 — Purpose:** Returns all active languages for frontend routing. Overrides base's `_get_frontend()` (which returns an empty dict) so that `http_routing` always has a language list available.

**L4 — Inherited from base:** The base `res.lang._get_frontend()` returns `{}` by default — `http_routing` overrides it to return all active languages. This is the hook that `website` module further customizes to filter languages per website.

---

## URL Localization

### `_url_localized(url, lang_code, canonical_domain, prefetch_langs, force_default_lang)`

```python
@classmethod
def _url_localized(cls,
        url: str | None = None,
        lang_code: str | None = None,
        canonical_domain: str | tuple[str, str, str, str, str] | None = None,
        prefetch_langs: bool = False,
        force_default_lang: bool = False) -> str:
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str \| None` | `None` | URL to localize. If `None`, uses current request path + query string |
| `lang_code` | `str \| None` | `None` | Target language code (e.g., `'fr_FR'`). If `None`, uses `request.lang` |
| `canonical_domain` | `str \| tuple` | `None` | Domain to prepend for canonical URLs (e.g., `https://example.com`) |
| `prefetch_langs` | `bool` | `False` | If `True`, preloads translation prefetch hints on record |
| `force_default_lang` | `bool` | `False` | If `True`, adds language prefix even for default language |

**L3 — Workflow:**
1. Resolve target `LangData` from `lang_code` or `request.lang`
2. If `url` is `None`, build from `request.httprequest.path` + `keep_query()`
3. Strip trailing `?` from URL (then reattach after processing)
4. Re-match the URL against the routing table to get the route rule and arguments
5. Translate model records in args to target language via `val.with_context(lang=lang.code)`
6. Rebuild the path using `router.build(rule.endpoint, args)` — this generates the slugified URL in target language
7. Prepend language prefix if needed

**L3 — User context preservation:** If the record's environment has a `RequestUID` (from `ModelConverter`), switches to `request.env.uid` before calling `with_context(lang=...)`. This ensures the language switch respects the authenticated user, not the converter's fake UID.

**L4 — Failure handling:** If re-matching fails (record not found, access denied), falls back to URL-quoting the original URL. Does not raise — silently degrades.

**L4 — `canonical_domain` tuple format:** The type annotation `tuple[str, str, str, str, str]` suggests a 5-element tuple (protocol, host, port, etc. from `urllib.parse.urlparse`). Pass a string like `'https://example.com'` and it will be parsed internally.

**L4 — `prefetch_langs`:** When `True`, passes `prefetch_langs=True` in the context, which hints to the ORM to preload translations for all frontend languages rather than just the current one. Reduces N+1 queries when building sitemap or language switcher.

---

### `_url_lang(path_or_uri, lang_code)` — Add/Remove Language Prefix

```python
@classmethod
def _url_lang(cls, path_or_uri: str, lang_code: str | None = None) -> str:
    ''' Given a relative URL, make it absolute and add the required lang or
        remove useless lang.
        Nothing will be done for absolute or invalid URL.
        If there is only one language installed, the lang will not be handled
        unless forced with `lang` parameter.
    '''
```

**L3 — Logic:**
1. Parses URL via `urllib.parse.urlparse`. Catches `ValueError` for malformed URLs (e.g., IPv6 edge cases)
2. Only processes relative URLs with a path component or when `lang_code` is explicitly provided
3. Uses `werkzeug.urls.url_join(request.httprequest.path, location)` to resolve relative URLs against current path
4. If more than one language installed OR `force_lang`, and URL is multilang:
   - If path already has a language code: replaces it if `force_lang=True`, otherwise removes default language code
   - If path has no language code: inserts target language code (unless it's the default and not forced)
5. Catches double slashes (`//`) in paths — normalizes them to single `/`

**L4 — Relative URL resolution:** `url_join('/shop/product', '../blog')` → `/shop/blog`. This means relative links in templates are correctly resolved regardless of current language context.

**L4 — Single-language behavior:** When only one language is installed, no prefix is added unless `lang_code` is explicitly passed (via `force_lang=True`). This prevents unnecessary `/en/` prefixes on single-language sites.

---

### `_url_for(url_from, lang_code)` — URL Rewriting

```python
@classmethod
def _url_for(cls, url_from: str, lang_code: str | None = None) -> str:
    ''' Return the url with the rewriting applied.
        Nothing will be done for absolute URL, invalid URL, or short URL from 1 char.
    '''
    return cls._url_lang(url_from, lang_code=lang_code)
```

**L3 — QWeb template usage:** This method is injected into QWeb templates as `url_for` (see `ir_qweb.py`). Usage: `<a t-att-href="url_for('/contact')">` or `<t t-esc="url_for('/page', 'fr_FR')"/>`.

**L4 — Short URL exception:** `_url_lang` silently returns unchanged URLs that don't parse as valid relative paths. This includes 1-char paths like `/x`.

---

## Routing Algorithm: `_match()`

The central routing method implements a **9-step state machine** with this signature:

```python
@classmethod
def _match(cls, path):
```

### Request Attributes Set

| Attribute | Set by | Type | Used for |
|-----------|--------|------|---------|
| `request.is_frontend` | `_match()` | `bool` | Whether request hits website (vs. backend/API) |
| `request.is_frontend_multilang` | `_match()` | `bool` | Whether the matched route supports multilingual URL rewriting |
| `request.lang` | `_match()` | `LangData` | The active language for this request |

### Step-by-Step Algorithm

```
Step 1:  Non-website endpoint → use as-is
Step 2:  No lang in URL + default lang → continue
Step 3:  Missing lang + bot UA → continue (save lang, no redirect)
Step 4:  No lang + POST request → continue (no redirect for POST)
Step 5:  Missing lang → redirect to /{lang}{path}   [302]
Step 6:  Default lang in URL → redirect to remove it [301]
Step 7:  Lang alias in URL → redirect to preferred code [301]
Step 8:  Homepage + trailing slash → remove slash   [301]
Step 9:  Valid lang in URL → rewrite URL, continue dispatch
```

### Double-Slash Normalization (Pre-Step)

```python
if allow_redirect and '//' in path:
    new_url = path.replace('//', '/')
    werkzeug.exceptions.abort(request.redirect(new_url, code=301, local=True))
```

**L4 — Security:** Double slashes can occur when URLs are concatenated in templates (e.g., `'/shop/' + '/product'`). This 301 redirect prevents search engines from indexing duplicate URLs and reduces path traversal confusion.

### Language Detection Priority

```python
nearest_url_lang  = get_nearest_lang(request.env['res.lang']._get_data(url_code=url_lang_str).code or url_lang_str)
cookie_lang      = get_nearest_lang(request.cookies.get('frontend_lang'))
context_lang     = get_nearest_lang(real_env.context.get('lang'))
default_lang     = cls._get_default_lang()
request.lang = request.env['res.lang']._get_data(code=(
    nearest_url_lang or cookie_lang or context_lang or default_lang.code
))
```

**L4 — URL vs. cookie:** URL language always takes priority when present. A URL with `/fr/...` will use French even if `frontend_lang` cookie says `de_DE`.

**L4 — Bot detection:** `is_a_bot()` checks `request.httprequest.user_agent.string` against known bot substrings. Bots get the default language without redirects — this prevents search engine crawlers from following redirect chains and ensures they index the canonical URL.

### Redirect Decision: `allow_redirect`

```python
allow_redirect = (
    request.httprequest.method != 'POST'
    and getattr(request, 'is_frontend_multilang', True)
)
```

**L4 — Security:** POST requests are never redirected because:
1. Browsers convert POST to GET on 302 redirects (losing POST data)
2. Redirecting POST would create a state-changing request that a user didn't initiate

**L4 — `is_frontend_multilang` default:** If not yet set (pre-`_match`), defaults to `True`, meaning redirects are allowed for any frontend request.

### Step 5: Missing Language → 302 Add Lang Prefix

```python
elif not url_lang_str:
    redirect = request.redirect_query(f'/{request_url_code}{path}', request.httprequest.args)
    redirect.set_cookie('frontend_lang', request.lang.code)
    werkzeug.exceptions.abort(redirect)
```

**HTTP Status:** 302 (Found) — temporary redirect preserving query string via `redirect_query()`

**Cookie:** Sets `frontend_lang` so subsequent requests don't trigger redirects

### Step 6: Default Language in URL → 301 Remove Prefix

```python
elif url_lang_str == default_lang.url_code and allow_redirect:
    redirect = request.redirect_query(path_no_lang, request.httprequest.args)
    redirect.set_cookie('frontend_lang', default_lang.code)
    werkzeug.exceptions.abort(redirect)
```

**HTTP Status:** 301 (Moved Permanently) — tells search engines the URL without default lang is canonical

**L4 — SEO:** Prevents duplicate content by ensuring only one canonical URL format per page

### Step 7: Language Alias → 301 Preferred Code

```python
elif url_lang_str != request_url_code and allow_redirect:
    redirect = request.redirect_query(f'/{request_url_code}{path_no_lang}', ..., code=301)
```

**L4 — Example:** `/fr_FR/shop` → `/fr/shop` (if `fr` is the preferred URL code for `fr_FR` language)

### Step 8: Homepage Trailing Slash → 301 Remove

```python
elif path == f'/{url_lang_str}/' and allow_redirect:
    redirect = request.redirect_query(path[:-1], ..., code=301)
    werkzeug.exceptions.abort(redirect)
```

**L4 — Edge case:** Only triggers for the homepage (`/`). Other pages with trailing slashes are handled as normal routes.

### Step 9: Valid Language → Rewrite and Dispatch

```python
elif url_lang_str == request_url_code:
    request.reroute(path_no_lang)  # removes lang prefix from URL path
    path = path_no_lang
```

**L4 — `reroute()`:** Internally calls `werkzeug.routing.Map.bind().match()` again with the rewritten path. The `rerouting_limit = 10` attribute prevents infinite loops from routes that re-add the language prefix.

**L4 — Path update:** Sets `path = path_no_lang` so the subsequent `super()._match(path)` uses the language-stripped path.

### Final Re-match and 404 Handling

```python
try:
    rule, args = super()._match(path)
    routing = rule.endpoint.routing
    request.is_frontend = routing.get('website', False)
    request.is_frontend_multilang = request.is_frontend and routing.get('multilang', routing['type'] == 'http')
    return rule, args
except NotFound:
    request.is_frontend = True
    request.is_frontend_multilang = True
    raise
```

**L4 — 404 as website page:** If the rewritten path raises `NotFound`, the request is promoted to a frontend request (`is_frontend=True`) and re-raised. This allows `website` module's error handler to serve a custom page or the 404 template, rather than returning a raw 404.

---

## Pre-dispatch: Slug Canonicalization

### `_pre_dispatch(rule, args)`

```python
@classmethod
def _pre_dispatch(cls, rule, args):
    super()._pre_dispatch(rule, args)  # handles debug mode, file upload limits

    if request.is_frontend:
        cls._frontend_pre_dispatch()

        # update the context of "<model(...):...>" args
        for key, val in list(args.items()):
            if isinstance(val, models.BaseModel):
                args[key] = val.with_context(request.env.context)
```

**L3 — Context propagation:** Each model record argument gets the full request environment context (including `lang`). This ensures the controller receives records already switched to the request's language.

### Canonical Slug Redirect

```python
if request.is_frontend_multilang:
    if request.httprequest.method in ('GET', 'HEAD'):
        _, path = rule.build(args)
        assert path is not None
        generated_path = werkzeug.urls.url_unquote_plus(path)
        current_path = werkzeug.urls.url_unquote_plus(request.httprequest.path)
        if generated_path != current_path:
            if request.lang != cls._get_default_lang():
                path = f'/{request.lang.url_code}{path}'
            redirect = request.redirect_query(path, request.httprequest.args, code=301)
            werkzeug.exceptions.abort(redirect)
```

**L3 — SEO canonical redirect:** If the URL a user visited doesn't match the canonical slug, a 301 redirect is issued.

**L4 — Examples:**

| Accessed URL | Record name | Generated path | Redirect |
|---|---|---|---|
| `/blog/1` | "My Blog Post" | `/blog/my-blog-post-1` | 301 to `/blog/my-blog-post-1` |
| `/fr/blog/1` | "Mon Article" | `/blog/mon-article-1` | 301 to `/fr/blog/mon-article-1` |
| `/shop/product-blue-17` | already correct | `/shop/product-blue-17` | No redirect |
| `/blog/my-old-slug-1` | record renamed | `/blog/new-name-1` | 301 to `/blog/new-name-1` |

**L4 — Performance:** `rule.build(args)` reconstructs the URL from the route's endpoint and arguments. This is a string concatenation operation — not a database query. The `assert path is not None` guards against werkzeug returning `None` in edge cases.

**L4 — `url_unquote_plus`:** Both paths are URL-decoded before comparison so `%20` spaces don't cause false negatives.

**L4 — Only GET/HEAD:** POST requests are never redirected here. Forms submitted to non-canonical URLs preserve their data.

---

### `_frontend_pre_dispatch()`

```python
@classmethod
def _frontend_pre_dispatch(cls):
    request.update_context(lang=request.lang.code)
    if request.cookies.get('frontend_lang') != request.lang.code:
        request.future_response.set_cookie('frontend_lang', request.lang.code)
```

**L3 — Purpose:** Called at the start of every frontend request to:
1. Set the ORM language context so all record fetches return translated names
2. Sync the `frontend_lang` cookie with the URL-determined language

**L4 — Cookie sync:** If URL says `fr` but cookie says `de`, the cookie is updated. This ensures subsequent backend-to-frontend navigation uses the URL's language.

---

## URL Rewrite with Caching

```python
@api.model
@tools.ormcache('path', 'query_args', cache='routing.rewrites')
def url_rewrite(self, path, query_args=None):
    new_url = False
    router = http.root.get_db_router(request.db).bind('')
    endpoint = False
    try:
        try:
            endpoint = router.match(path, method='POST', query_args=query_args)
        except werkzeug.exceptions.MethodNotAllowed:
            endpoint = router.match(path, method='GET', query_args=query_args)
    except werkzeug.routing.RequestRedirect as e:
        new_url = e.new_url.split('?')[0][7:]  # remove scheme
        _, endpoint = self.url_rewrite(new_url, query_args)
        endpoint = endpoint and [endpoint]
    except werkzeug.exceptions.NotFound:
        new_url = path
    return new_url or path, endpoint and endpoint[0]
```

**L4 — Cache configuration:** `cache='routing.rewrites'` uses Odoo's named cache pool. Cache is database-persistent across requests and invalidated when module code changes.

**L4 — Cache key:** `(path, query_args)` — path must be a string. `query_args` can be `None`, a string, or a dict.

**L4 — `RequestRedirect` handling:** If werkzeug raises a redirect during matching, the new URL is extracted (scheme removed, path kept) and recursively rewritten. `endpoint = endpoint and [endpoint]` converts `None` or an endpoint to a list or `None` — used downstream to check truthiness.

**L4 — Return type:** `(new_url_or_path: str, endpoint: werkzeug.routing.Rule | None)`

---

## Error Handling

### `_get_exception_code_values(exception)`

```python
@classmethod
def _get_exception_code_values(cls, exception):
    code = 500  # default code
    values = dict(
        exception=exception,
        traceback=''.join(traceback.format_exception(exception)),
    )

    if isinstance(exception, exceptions.UserError):
        code = exception.http_status
        values['error_message'] = exception.args[0]
    elif isinstance(exception, werkzeug.exceptions.HTTPException):
        code = exception.code
        values['error_message'] = exception.description

    if hasattr(exception, 'qweb'):
        values.update(qweb_exception=exception.qweb)
        if code == 404 and exception.qweb.path:
            # If there is a path, the error does not come from the called template
            # (e.g. a "/t" from a t-call MissingError)
            code = 500

    values.update(
        status_message=werkzeug.http.HTTP_STATUS_CODES.get(code, ''),
        status_code=code,
    )

    return (code, values)
```

**L3 — Exception → HTTP status mapping:**

| Exception type | HTTP code | Notes |
|---|---|---|
| `exceptions.UserError` | `exception.http_status` (custom attribute) | e.g., `ValidationError` |
| `werkzeug.exceptions.HTTPException` subclasses | `exception.code` | 400, 403, 404, etc. |
| QWeb error with template path | 404 → 500 | Template rendering failures become 500 |
| Any other exception | 500 | Internal error |

**L4 — QWeb 404 → 500 promotion:** If a QWeb exception has a `path` attribute, the error is not from the primary template but from a nested `t-call`. In this case, the 404 becomes a 500 to avoid leaking template structure information.

---

### `_get_values_500_error(env, values, exception)`

```python
@classmethod
def _get_values_500_error(cls, env, values, exception):
    values['view'] = env["ir.ui.view"]
    return values
```

**L3 — Purpose:** Adds the `ir.ui.view` model to the template context for 500 errors, enabling the error template to access view information.

---

### `_get_error_html(env, code, values)`

```python
@classmethod
def _get_error_html(cls, env, code, values):
    try:
        return code, env['ir.ui.view']._render_template('http_routing.%s' % code, values)
    except MissingError:
        if str(code)[0] == '4':
            return code, env['ir.ui.view']._render_template('http_routing.4xx', values)
        raise
```

**L3 — Template fallback chain:**
1. Try `http_routing.{code}` — e.g., `http_routing.404`, `http_routing.500`
2. If `MissingError` (template doesn't exist) and code starts with `4` (4xx range):
   - Fall back to `http_routing.4xx` generic template
3. If not a 4xx code or generic template missing: re-raise

**L4 — Template-based rendering:** Uses `_render_template` (low-level, no controller context) instead of `render()` to avoid circular dependencies during error rendering.

---

### `_handle_error(exception)`

```python
@classmethod
def _handle_error(cls, exception):
    response = super()._handle_error(exception)

    is_frontend_request = bool(getattr(request, 'is_frontend', False))
    if not is_frontend_request or not isinstance(response, HTTPException):
        return response

    # minimal setup to serve frontend pages
    if not request.env.uid:
        cls._auth_method_public()
    cls._handle_debug()
    cls._frontend_pre_dispatch()
    request.params = request.get_http_params()

    code, values = cls._get_exception_code_values(exception)

    request.env.cr.rollback()
    if code in (404, 403):
        try:
            response = cls._serve_fallback()  # Try website page
            if response:
                cls._post_dispatch(response)
                return response
        except werkzeug.exceptions.Forbidden:
            pass  # Use default error page handling.
    elif code == 500:
        values = cls._get_values_500_error(request.env, values, exception)
    try:
        code, html = cls._get_error_html(request.env, code, values)
    except Exception:
        _logger.exception("Couldn't render a template for http status %s", code)
        code, html = 418, request.env['ir.ui.view']._render_template('http_routing.http_error', values)

    response = Response(html, status=code, content_type='text/html;charset=utf-8')
    cls._post_dispatch(response)
    return response
```

**L3 — `_serve_fallback()`:** This method (defined in `website` module, called here via duck typing) checks if there's a website page matching the requested path and serves it as a fallback. This enables `/page/about` to work even if the controller is missing, by serving the CMS page directly.

**L4 — Database rollback:** `request.env.cr.rollback()` is called before rendering error pages to ensure the error state doesn't leave uncommitted transactions that could corrupt subsequent requests.

**L4 — 418 fallback:** If error template rendering itself fails, returns HTTP 418 (I'm a Teapot) with a minimal fallback template. This prevents the error handler from infinitely recursing.

**L4 — `request.get_http_params()`:** Collects all HTTP GET/POST parameters into `request.params` for use in error context — allows error pages to show submitted form data (sanitized).

---

## Frontend Session Info

```python
@api.model
def get_frontend_session_info(self) -> dict:
    session_info = super(IrHttp, self).get_frontend_session_info()

    if request.is_frontend:
        lang = request.lang.code
        session_info['bundle_params']['lang'] = lang
    session_info.update({
        'translationURL': '/website/translations',
    })
    return session_info
```

**L3 — Session info additions:**
- `bundle_params['lang']`: Language code passed to Webpack asset bundler for locale-aware JS
- `translationURL`: Endpoint for lazy-loading frontend translation files

**L4 — Odoo 18→19 change:** In Odoo 18, `translationURL` was not included in session info — translations were bundled statically. Odoo 19 added lazy translation loading via `/website/translations`.

---

## Translation Frontend Modules

```python
@api.model
def get_translation_frontend_modules(self) -> list[str]:
    Modules = request.env['ir.module.module'].sudo()
    extra_modules_name = self._get_translation_frontend_modules_name()
    extra_modules_domain = Domain(self._get_translation_frontend_modules_domain())
    if not extra_modules_domain.is_true():
        new = Modules.search(extra_modules_domain & Domain('state', '=', 'installed')).mapped('name')
        extra_modules_name += new
    return extra_modules_name

@classmethod
def _get_translation_frontend_modules_domain(cls) -> list[tuple[str, str, typing.Any]]:
    return []  # Default: no extra modules

@classmethod
def _get_translation_frontend_modules_name(cls) -> list[str]:
    return ['web']  # Always include 'web'
```

**L4 — Purpose:** Returns the list of modules whose translations should be loaded on the frontend. The `website` module overrides `_get_translation_frontend_modules_domain()` to add all installed website-compatible modules.

---

## QWeb Extension: `ir_qweb.py`

```python
class IrQweb(models.AbstractModel):
    _inherit = "ir.qweb"

    def _prepare_environment(self, values):
        irQweb = super()._prepare_environment(values)
        values['slug'] = self.env['ir.http']._slug
        values['unslug_url'] = self.env['ir.http']._unslug_url

        if not irQweb.env.context.get('minimal_qcontext') and request:
            if not hasattr(request, 'is_frontend'):
                _logger.warning(BAD_REQUEST, stack_info=True)
            elif request.is_frontend:
                return irQweb._prepare_frontend_environment(values)

        return irQweb

    def _prepare_frontend_environment(self, values):
        values['url_for'] = self.env['ir.http']._url_for
        values['url_localized'] = self.env['ir.http']._url_localized
        return self
```

**L3 — Template functions available:**

| Function | Defined in | Available in |
|----------|-----------|-------------|
| `slug(record)` | `ir_qweb._prepare_environment` | All QWeb environments |
| `unslug_url(path)` | `ir_qweb._prepare_environment` | All QWeb environments |
| `url_for(url)` | `ir_qweb._prepare_frontend_environment` | Frontend only |
| `url_localized(url, lang)` | `ir_qweb._prepare_frontend_environment` | Frontend only |

**L4 — `minimal_qcontext`:** When rendering without a full template context (e.g., email templates), this flag prevents frontend-specific functions from being injected, avoiding unnecessary request dependencies.

**L4 — BAD_REQUEST warning:** If `request.is_frontend` is not set but `http_routing` is installed, logs a warning. This catches `@route(auth='none')` controllers that create their own registry and try to render templates without going through the normal routing pipeline.

---

## Controllers

### `Routing` — Translation Endpoint

```python
class Routing(Home):
    @http.route('/website/translations', type='http', auth="public", website=True, readonly=True, sitemap=False)
    def get_website_translations(self, hash=None, lang=None, mods=None):
        IrHttp = request.env['ir.http'].sudo()
        modules = IrHttp.get_translation_frontend_modules()
        if mods:
            modules += mods.split(',')
        return WebClient().translations(hash, mods=','.join(modules), lang=lang)
```

**L3 — Purpose:** Serves lazy-loaded translation files for frontend modules.

**L3 — Parameters:**
- `hash`: Cache validation hash (returns 304 Not Modified if match)
- `lang`: Target language code
- `mods`: Comma-separated additional module names to include

**L3 — `readonly=True`:** Route is marked as read-only (safe to cache at CDN level)

**L3 — `sitemap=False`:** Excluded from sitemap generation

---

### `SessionWebsite` — Logout Override

```python
class SessionWebsite(Session):
    @http.route('/web/session/logout', website=True, multilang=False, sitemap=False)
    def logout(self, redirect='/odoo'):
        return super().logout(redirect=redirect)
```

**L3 — Override purpose:** Adds `multilang=False` to prevent language prefix from being injected into the logout URL. The base `Session.logout` already handles the redirect.

**L4 — `multilang=False`:** Explicitly tells `_is_multilang_url()` this route is not translatable, preventing language prefix logic from running.

---

## Error Page Templates

**File:** `views/http_routing_template.xml`

| Template ID | HTTP Code | Purpose |
|-------------|-----------|---------|
| `http_routing.http_error` | generic | Generic fallback for all errors |
| `http_routing.4xx` | 4xx range | Catch-all for client errors |
| `http_routing.400` | 400 Bad Request | Malformed request |
| `http_routing.403` | 403 Forbidden | Access denied |
| `http_routing.404` | 404 Not Found | Missing page — includes 404 SVG graphic and "popular pages" links |
| `http_routing.415` | 415 Unsupported Media Type | Unsupported format |
| `http_routing.422` | 422 Unprocessable Entity | Validation errors |
| `http_routing.500` | 500 Internal Server Error | App errors — uses raw Bootstrap (no theme) to avoid broken rendering |

**L4 — 500 template constraints:** The comment at line 193-197 notes this template must not use any variables except those provided by `_handle_exception`, must not use `request.csrf_token`, must not load theme assets — because the cursor may be broken during rendering. Uses raw Bootstrap CSS/JS from `/web/static/lib/`.

**L4 — Debug mode:** In editable or debug mode, all error templates display the `http_error_debug` section with collapsible cards showing error message, QWeb exception details, and full traceback.

---

## `res.lang` Views

**File:** `views/res_lang_views.xml`

Adds `url_code` field to both form and tree views of `res.lang`:

```xml
<field name="url_code" required="0"/>  <!-- form: always visible -->
<field name="url_code" groups="base.group_no_one"/>  <!-- tree: admin only -->
```

**L3 — `url_code` vs. `code`:** `res.lang.code` is the locale code (e.g., `fr_FR`), used internally. `url_code` is the URL-safe version (e.g., `fr`), used in language prefixes. Both can be different — e.g., language with code `pt_BR` might have URL code `br` or `pt-br`.

**L4 — Access control:** The `url_code` field in the tree view is restricted to `base.group_no_one` (technical features group), preventing regular admins from seeing/modifying URL codes.

---

## Extension Points

### Custom Slug Formats

Override in custom module:

```python
class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _slug(cls, value):
        result = super()._slug(value)
        # Add prefix or modify slug
        return f"custom-{result}"
```

**L4 — Performance note:** `_slug` is called for every URL generation. Adding a database lookup here would add overhead per request. Keep overrides lightweight.

### Custom URL Converters

```python
from odoo.addons.http_routing.models.ir_http import ModelConverter

@http.route('/my-route/<model("my.model"):record>', type='http', website=True, auth='public')
def my_route(self, record, **kwargs):
    return request.render('my_module.record_page', {'record': record})
```

### Custom Error Pages

Create template `http_routing.404` in your module:

```xml
<template id="404" name="Custom 404">
    <t t-call="website.layout">
        <div class="oe_404">
            <h1>Page Not Found</h1>
            <p>The page you are looking for does not exist.</p>
        </div>
    </t>
</xml>
```

### Override `_is_multilang_url`

To mark custom routes as non-translatable:

```python
@classmethod
def _is_multilang_url(cls, local_url, lang_url_codes=None):
    result = super()._is_multilang_url(local_url, lang_url_codes)
    if local_url.startswith('/my-api/'):
        return False
    return result
```

### Override `_get_default_lang`

For multi-website scenarios, override to return website-specific default:

```python
@classmethod
def _get_default_lang(cls):
    website = request.env['website'].get_current_website()
    if website.default_lang_id:
        return website.default_lang_id
    return super()._get_default_lang()
```

---

## Language Detection Order (Final Summary)

```
1. URL path language code  (nearest_url_lang)     ← highest priority
2. frontend_lang cookie    (cookie_lang)
3. request.env.context['lang'] (context_lang)
4. ir.default for res.partner.lang  →  first active language (default_lang)
```

**L4 — Context vs. cookie:** If a user visits `/fr/shop` (URL sets French), the cookie will be updated to `fr_FR`. On subsequent direct navigation to `/shop` (no URL lang), the cookie's French is used. But a URL with a language always wins over cookie.

---

## Performance: Caching Summary

| Cached Item | Cache Key | TTL | Purpose |
|-------------|-----------|-----|---------|
| `url_rewrite()` | `(path, query_args)` | Persistent (module reload invalidates) | Fast URL → endpoint lookups |
| `res.lang._get_active_by('code')` | internal ORM cache | Persistent | Language list |
| `request.lang._get_data(code=...)` | ORM cache | Persistent | Language metadata |
| Record `display_name` | Recordset cache | Transaction | Slug generation |

**L4 — `ormcache` context:** `url_rewrite` uses `cache='routing.rewrites'` which is a named cache pool. In multi-instance deployments, this cache is instance-local and survives request boundaries.

**L4 — Invalidation:** The cache is invalidated when the module registry is rebuilt (after installing/upgrading a module). For organic URL changes (record renamed), the cache naturally resolves via `rule.build(args)` generating fresh slugs.

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| **Redirect loops** | `rerouting_limit = 10` prevents infinite redirect cycles |
| **POST data loss on redirect** | `allow_redirect = False` for POST requests |
| **CSRF on auth='none' routes** | Base `ir.http._authenticate` enforces CSRF for non-public routes. `http_routing` adds no CSRF weakening. |
| **Double-slash path traversal** | Normalized to single slash via 301 redirect before routing |
| **Language enumeration** | `url_code` field is hidden from non-admin users in list view |
| **Error page information leakage** | QWeb errors with `path` attribute are promoted to 500, preventing template structure disclosure |
| **Cookie manipulation** | `frontend_lang` cookie is set server-side, not derived from user input |

---

## Odoo 18 → 19 Changes

| Feature | Odoo 18 | Odoo 19 |
|---------|---------|---------|
| Default language detection | First alphabetically active language | `ir.default` for `res.partner.lang` first |
| Translation loading | Static bundle | Lazy via `/website/translations` endpoint |
| Frontend session info | Basic session data | Includes `translationURL`, `bundle_params.lang` |
| `_slug` error message | `%s` formatting | f-string interpolation |
| Bot handling | No special bot handling in routing | Bots get default lang without redirect (Step 3) |
| 404 → 500 for QWeb errors | Not documented in `http_routing` | Explicit logic in `_get_exception_code_values()` |
| `_url_localized` | Basic path rebuilding | Added `canonical_domain`, `prefetch_langs`, `force_default_lang` |

---

## Notes

- The module's sequence of **9100** means it loads very late — after `website` and `portal` are fully initialized
- Slug canonicalization only triggers on **GET/HEAD** requests (never on POST/PUT/DELETE)
- Bots (Googlebot, Facebook crawler, etc.) get the default language without redirects — this prevents crawl traps
- Double-hyphen `--` in URLs encodes negative IDs (e.g., `--42` → ID -42) as a fallback heuristic
- The `translationURL` in frontend session info enables lazy translation loading, reducing initial bundle size
- Error pages attempt `website._serve_fallback()` first (for 404/403) before rendering the error template
- `url_for` and `url_localized` are only injected into QWeb environments when `request.is_frontend` is True
- The `BAD_REQUEST` warning in `ir_qweb.py` catches `@route(auth='none')` controllers that bypass routing
- `ModelConverter.to_python` uses a fake `RequestUID` environment to browse records without full user context

## Related Documentation

- [Modules/web](modules/web.md) — Base web module (dependency), provides `is_a_bot`, debug handling, session info
- [Modules/website](modules/website.md) — Website builder, extends routing with page serving and fallback handling
- [Core/HTTP Controller](core/http-controller.md) — HTTP routing and controllers architecture
- [ir.http](ir.http.md) — Base HTTP routing model (in `odoo/addons/base`)
- [Patterns/Inheritance Patterns](patterns/inheritance-patterns.md) — `_inherit` vs. `_inherits` for model extension patterns