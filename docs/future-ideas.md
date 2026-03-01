# Future Ideas — The War Table

Ideas that are intentionally deferred. Not forgotten — just waiting for the right phase.

---

## Theme Engine

**Why deferred:** A single high-contrast CSS toggle is not the right approach. Adding one-off overrides creates maintenance debt and doesn't scale.

**The right approach:** A proper theme engine where:
- Each theme is a named CSS variable set (or a separate CSS file)
- Themes are stored in `AppSetting` as `ui_theme = 'dark' | 'high_contrast' | 'light' | ...`
- The active theme is applied via a `data-theme` attribute on `<html>` (or a CSS class)
- `base.html` reads the theme from a context processor injected in `app/__init__.py`
- Settings page lets the user pick a theme from a dropdown or visual swatch
- New themes can be added by dropping a new CSS file into `app/static/css/themes/`

**Supported themes to build toward:**
- `dark` — current default
- `high_contrast` — brighter text, sharper borders, for use at dim game tables
- `light` — for daytime use or accessibility preference
- `parchment` — sepia/fantasy aesthetic (stretch goal)

**Notes:**
- Bootstrap 5.3 `data-bs-theme` only supports `light` and `dark` natively; custom themes need CSS custom property overrides
- Consider using CSS `@layer` to keep theme overrides isolated from component styles
- No migrations needed — `AppSetting` model already exists
