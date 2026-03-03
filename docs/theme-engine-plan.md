# Theme Engine

## Context

The War Table is always used on a dark theme. Craig wants a way to switch between themes — **dark** (current), **light** (daytime), **high contrast** (dim game tables), and eventually **parchment** (fantasy aesthetic). The app uses Bootstrap 5.3.3 with `data-bs-theme="dark"` hardcoded on `<html>`, plus 127 lines of custom CSS with 5 hardcoded color values. There are ~267 uses of `bg-dark` and ~163 uses of `text-light` across 70+ templates.

**Branch:** `feature/theme-engine`

---

## Core Design Decisions

### The Bootstrap utility class problem

Templates are full of `bg-dark`, `text-light`, `table-dark`, `dropdown-menu-dark`, `navbar-dark`. These **fight** a light theme because they're hardcoded dark regardless of `data-bs-theme`.

**Solution:** CSS overrides that neutralize these classes when a non-dark theme is active. Zero template changes needed. Example: `[data-bs-theme="light"] .bg-dark { background-color: var(--bs-body-bg) !important; }`. The dark theme remains byte-for-byte identical.

### Dual-attribute approach for custom themes

Bootstrap only recognizes `data-bs-theme="dark"` and `"light"`. For high_contrast and parchment, we use **two attributes**:
- `data-bs-theme` = `"dark"` or `"light"` (tells Bootstrap which base to use)
- `data-wt-theme` = `"dark"`, `"light"`, `"high_contrast"`, `"parchment"` (our custom layer)

High contrast builds on dark. Parchment builds on light. CSS selectors use `[data-wt-theme="high_contrast"]`.

### Storage: localStorage + AppSetting default

- **localStorage** (`wt_theme` key) stores the per-browser choice. Good for game tables where the GM might want dark on the laptop and high-contrast on the tablet.
- **AppSetting** (`ui_default_theme`) sets what new browsers see. Admin sets this in Settings.
- No migration needed.

---

## Files to Create/Modify

| File | Action | Summary |
|------|--------|---------|
| `app/static/css/custom.css` | Modify | Convert 5 hardcoded colors to `--wt-*` CSS custom properties |
| `app/static/css/themes.css` | **Create** | All theme variable definitions + utility class overrides (~120 lines) |
| `app/static/js/theme_toggle.js` | **Create** | Theme switching, localStorage persistence, icon/dropdown state |
| `app/templates/includes/theme_head.html` | **Create** | Anti-FOUC script + theme CSS link (shared by both base templates) |
| `app/templates/base.html` | Modify | Dynamic attributes, include theme_head, add toggle dropdown in navbar |
| `app/templates/wiki/base_wiki.html` | Modify | Same dynamic attributes + include theme_head |
| `app/__init__.py` | Modify | Add `inject_theme` context processor (~10 lines) |
| `app/routes/settings.py` | Modify | Save/load `ui_default_theme` (2 lines) |
| `app/templates/settings/index.html` | Modify | Add Appearance card with default theme dropdown |
| `app/static/js/shortcode.js` | Modify | Replace ~15 inline style colors with Bootstrap classes |
| `app/static/js/entity_from_selection.js` | Modify | Replace inline style colors with Bootstrap classes |

**No migration needed.**

---

## Step 1: Convert custom.css to CSS custom properties

**File:** `app/static/css/custom.css`

Replace the 5 hardcoded hex colors with `--wt-*` variables, defined inside `[data-wt-theme="dark"]`:

```css
/* Theme-aware custom properties */
[data-wt-theme="dark"] {
    --wt-body-bg: #1a1a2e;
    --wt-card-bg: #16213e;
    --wt-card-border: #0f3460;
    --wt-link-color: #e94560;
    --wt-link-hover: #ff6b6b;
    --wt-session-navbar-bg: #2c3e50;
    --wt-session-accent: #e74c3c;
}

body { background-color: var(--wt-body-bg); ... }
.card { background-color: var(--wt-card-bg); border-color: var(--wt-card-border); }
a { color: var(--wt-link-color); }
a:hover { color: var(--wt-link-hover); }
```

Dark theme looks identical — same values, just through variables now.

---

## Step 2: Create themes.css

**New file:** `app/static/css/themes.css` — one file for all themes (small, avoids extra HTTP requests)

### Light theme section
```css
[data-wt-theme="light"] {
    --wt-body-bg: #f8f9fa;
    --wt-card-bg: #ffffff;
    --wt-card-border: #dee2e6;
    --wt-link-color: #c0392b;
    --wt-link-hover: #e74c3c;
    --wt-session-navbar-bg: #34495e;
    --wt-session-accent: #e74c3c;
}

/* Neutralize dark utility classes for light themes */
[data-bs-theme="light"] .bg-dark { background-color: var(--bs-body-bg) !important; }
[data-bs-theme="light"] .text-light { color: var(--bs-body-color) !important; }
[data-bs-theme="light"] .table-dark {
    --bs-table-bg: var(--bs-body-bg);
    --bs-table-color: var(--bs-body-color);
}
[data-bs-theme="light"] .navbar-dark { ... }
[data-bs-theme="light"] .dropdown-menu-dark { ... }
[data-bs-theme="light"] .form-control.bg-dark { background-color: var(--bs-body-bg) !important; color: var(--bs-body-color) !important; }
[data-bs-theme="light"] .form-select.bg-dark { background-color: var(--bs-body-bg) !important; color: var(--bs-body-color) !important; }
```

### High contrast section
```css
[data-wt-theme="high_contrast"] {
    --bs-body-bg: #000000;
    --bs-body-color: #ffffff;
    --bs-border-color: #ffffff;
    --wt-body-bg: #000000;
    --wt-card-bg: #0a0a0a;
    --wt-card-border: #ffffff;
    --wt-link-color: #ff6b6b;
    --wt-link-hover: #ff9999;
}
```
(Builds on Bootstrap dark — `bg-dark` classes are fine as-is)

### Parchment section (stretch goal)
```css
[data-wt-theme="parchment"] {
    --wt-body-bg: #f5e6c8;
    --wt-card-bg: #fdf5e6;
    --wt-card-border: #c4a882;
    --wt-link-color: #8b0000;
    --wt-link-hover: #b22222;
}
/* Same utility class neutralization as light theme */
```

---

## Step 3: Anti-FOUC script + shared include

**New file:** `app/templates/includes/theme_head.html`

```html
<script>
(function() {
    var theme = localStorage.getItem('wt_theme') || '{{ default_theme }}';
    var bsMap = { dark: 'dark', light: 'light', high_contrast: 'dark', parchment: 'light' };
    document.documentElement.setAttribute('data-bs-theme', bsMap[theme] || 'dark');
    document.documentElement.setAttribute('data-wt-theme', theme);
})();
</script>
<link rel="stylesheet" href="{{ url_for('static', filename='css/themes.css') }}">
```

This goes in `<head>` **before** any rendering. Prevents flash of wrong theme.

---

## Step 4: Update base.html

**File:** `app/templates/base.html`

1. Change `<html lang="en" data-bs-theme="dark">` → `<html lang="en" data-bs-theme="dark" data-wt-theme="dark">`
   (The anti-FOUC script overwrites these immediately, but they serve as no-JS fallback)

2. After the `custom.css` link, add: `{% include 'includes/theme_head.html' %}`

3. Add theme toggle dropdown in the navbar right side (near the user dropdown):
```html
<li class="nav-item dropdown">
    <a class="nav-link" href="#" data-bs-toggle="dropdown" title="Theme">
        <i class="bi bi-moon-fill" id="theme-toggle-icon"></i>
    </a>
    <ul class="dropdown-menu dropdown-menu-end dropdown-menu-dark">
        <li><a class="dropdown-item" href="#" data-theme-value="dark"><i class="bi bi-moon-fill me-2"></i>Dark</a></li>
        <li><a class="dropdown-item" href="#" data-theme-value="light"><i class="bi bi-sun-fill me-2"></i>Light</a></li>
        <li><a class="dropdown-item" href="#" data-theme-value="high_contrast"><i class="bi bi-eye-fill me-2"></i>High Contrast</a></li>
    </ul>
</li>
```

4. Add `<script src="{{ url_for('static', filename='js/theme_toggle.js') }}"></script>` before `</body>`

---

## Step 5: Context processor

**File:** `app/__init__.py` — add after existing context processors (~line 342):

```python
@app.context_processor
def inject_theme():
    from app.models import AppSetting
    default_theme = AppSetting.get('ui_default_theme', 'dark')
    return dict(default_theme=default_theme)
```

---

## Step 6: Settings page

**File:** `app/routes/settings.py` — POST handler add:
```python
AppSetting.set('ui_default_theme', request.form.get('ui_default_theme', 'dark'))
```

GET handler add:
```python
current_default_theme = AppSetting.get('ui_default_theme', 'dark')
```

**File:** `app/templates/settings/index.html` — add "Appearance" card with a default theme dropdown

---

## Step 7: Wiki base template

**File:** `app/templates/wiki/base_wiki.html` — same changes as base.html:
- Dynamic `data-bs-theme` / `data-wt-theme` attributes
- `{% include 'includes/theme_head.html' %}`
- Simplified theme toggle (icon only, no settings link)

---

## Step 8: Fix JS hardcoded colors

**File:** `app/static/js/shortcode.js` (~15 inline color references)
**File:** `app/static/js/entity_from_selection.js`

Replace inline `style.background = '#2a2a3e'` with Bootstrap utility classes (`bg-body-secondary`, `border`, `text-body`). More maintainable than reading CSS variables at runtime.

---

## Implementation Order

1. custom.css variable conversion (backward-compatible, zero visual change)
2. themes.css with dark variables (confirm existing look works through variables)
3. Anti-FOUC script + context processor (infrastructure)
4. Theme toggle UI in navbar (user-facing)
5. Light theme variables + utility class overrides (first new theme)
6. High contrast theme
7. Settings page default theme
8. Wiki base template
9. JS file color fixes (shortcode.js, entity_from_selection.js)
10. Parchment theme (stretch goal, can be a follow-up)

---

## Verification

1. Toggle to each theme via navbar → verify colors change instantly, no page reload
2. Refresh the page → theme persists (localStorage)
3. Open a new incognito window → falls back to admin default theme (AppSetting)
4. Dark theme must look **identical** to current app (no visual regression)
5. Light theme: cards, forms, tables, navbar should all be readable with proper contrast
6. High contrast: sharp white borders on black, brighter text, usable in dim lighting
7. Test on tablet viewport (768px) → toggle is accessible, themes render correctly
8. Test Session Mode → session mode navbar colors adapt per theme
9. Test wiki/player view → theme toggle works independently
10. Test shortcode popups and entity-from-selection panel → colors follow theme
