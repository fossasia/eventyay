# Token-Based Theming System - Implementation Guide

## Overview

The Eventyay platform now features a comprehensive token-based theming system that enables:

- **Centralized Design Control**: Define visual properties once as tokens
- **Consistent Styling**: All components automatically use the same tokens
- **Runtime Theme Switching**: Change themes without rebuilding the application
- **Multi-Level Customization**: Base → Organization → Event level overrides
- **Light/Dark Mode Support**: Automatic dark mode variants
- **Accessibility**: Built-in WCAG AA color contrast options

## Architecture

### Core Components

```
eventyay-common/theme/
├── default_tokens.json      # Base token definitions
├── overrides_schema.json    # Validation schema for user overrides
├── loader.py               # Token loading and merging logic
├── theme.ts                # Frontend theme manager
└── __init__.py

Models:
├── OrganizerTheme          # Organization-level theme
└── EventTheme              # Event-level theme (inherits from org)

API:
├── OrganizerThemeViewSet   # Org theme management endpoints
└── EventThemeViewSet       # Event theme management endpoints
```

## Design Token Structure

### Foundation Tokens

tokens organized by category:

```json
{
  "colors": {
    "primary": "#EB2188",
    "secondary": "#3B82F6",
    "success": "#10B981",
    "warning": "#F59E0B",
    "error": "#EF4444"
  },
  "typography": {
    "fontFamily": {
      "body": "Inter, sans-serif",
      "heading": "Poppins, sans-serif"
    },
    "fontSize": {
      "xs": "12px",
      "sm": "14px",
      "base": "16px",
      "lg": "18px"
    }
  },
  "spacing": {
    "1": "4px",
    "2": "8px",
    "4": "16px",
    "6": "24px"
  },
  "borderRadius": {
    "sm": "4px",
    "md": "8px",
    "lg": "12px"
  },
  "shadows": {
    "sm": "0 1px 2px rgba(0,0,0,0.05)",
    "md": "0 4px 6px rgba(0,0,0,0.1)"
  }
}
```

### Semantic Tokens

Higher-level aliases for component-specific styling:

```json
{
  "semanticTokens": {
    "button": {
      "primary": {
        "background": "{colors.primary}",
        "foreground": "{colors.textInverse}",
        "backgroundHover": "{colors.primaryDark}"
      }
    },
    "input": {
      "background": "{colors.surface}",
      "border": "{colors.border}",
      "borderFocus": "{colors.primary}"
    },
    "card": {
      "background": "{colors.surface}",
      "border": "{colors.border}",
      "shadow": "{shadows.md}"
    }
  }
}
```

## Usage Guide

### Backend (Python)

#### Loading and Merging Tokens

```python
from eventyay.eventyay_common.theme.loader import ThemeTokenLoader

# Load base tokens
base = ThemeTokenLoader.load_base_tokens()

# Load tokens with org overrides
org_tokens = ThemeTokenLoader.get_merged_tokens(
    base_overrides={'colors': {'primary': '#FF0000'}}
)

# Get tokens with full precedence (org + event)
event_tokens = ThemeTokenLoader.get_merged_tokens(
    base_overrides=org_overrides,
    event_overrides=event_overrides
)
```

#### Working with Models

```python
from eventyay.eventyay_common.models import OrganizerTheme, EventTheme

# Get or create organizer theme
theme = OrganizerTheme.objects.get_or_create(organizer=org)[0]

# Update primary color
theme.update_color('primary', '#FF0000')

# Get effective tokens (with merging)
event_theme = EventTheme.objects.get(event=event)
tokens = event_theme.get_effective_tokens()

# Export/Import
json_str = theme.export_as_json()
theme.import_from_json(json_str)
```

### Frontend (JavaScript/TypeScript)

#### Loading Themes

```typescript
import { themeManager, loadEventTheme, useTheme } from '@/theme';

// Load event theme from API
await loadEventTheme('organizer-slug', 'event-slug');

// Set color mode
themeManager.setColorMode('dark');

// Get current theme
const { tokens, isDark, colorMode } = useTheme();
```

#### Using Tokens in Components

```typescript
// Access token values
const primaryColor = themeManager.getToken('colors.primary');

// Update token at runtime
themeManager.updateToken('colors.primary', '#FF0000');

// Toggle dark mode
themeManager.setColorMode(themeManager.isDarkMode() ? 'light' : 'dark');
```

### Styling with Tokens

#### SCSS Approach

```scss
// Import the token variables
@import '@/scss/theme-tokens';

// Use token variables in your styles
.button {
  background-color: $button-primary-bg;
  color: $button-primary-text;
  border-radius: $radius-md;
  padding: $space-4;
  
  &:hover {
    background-color: $button-primary-bg-hover;
  }
}
```

#### CSS Approach (Recommended)

```css
/* Use CSS variables directly - no compilation needed */
.button {
  background-color: var(--color-primary);
  color: var(--color-text-inverse);
  padding: var(--spacing-4);
  border-radius: var(--borderRadius-md);
}

/* Automatic dark mode support */
[data-theme="dark"] .button {
  background-color: var(--darkMode-colors-primary);
  color: var(--darkMode-colors-text-inverse);
}
```

## API Endpoints

### Organizer Theme

```
GET    /api/orga/{organizer_slug}/theme/
PUT    /api/orga/{organizer_slug}/theme/
POST   /api/orga/{organizer_slug}/theme/update-token/
POST   /api/orga/{organizer_slug}/theme/export/
POST   /api/orga/{organizer_slug}/theme/import/
```

### Event Theme

```
GET    /api/orga/{organizer_slug}/events/{event_slug}/theme/
PUT    /api/orga/{organizer_slug}/events/{event_slug}/theme/
POST   /api/orga/{organizer_slug}/events/{event_slug}/theme/update-token/
POST   /api/orga/{organizer_slug}/events/{event_slug}/theme/preview/
POST   /api/orga/{organizer_slug}/events/{event_slug}/theme/reset/
POST   /api/orga/{organizer_slug}/events/{event_slug}/theme/export/
POST   /api/orga/{organizer_slug}/events/{event_slug}/theme/import/
```

## Customization Examples

### Example 1: Change Primary Color

```python
from eventyay.eventyay_common.models import EventTheme

event_theme = EventTheme.objects.get(event=event)
event_theme.update_color('primary', '#FF0000')
```

### Example 2: Apply Custom Fonts

```python
theme = EventTheme.objects.get(event=event)
theme.token_overrides = {
    'typography': {
        'fontFamily': {
            'body': '"Open Sans", sans-serif',
            'heading': '"Playfair Display", serif'
        }
    }
}
theme.save()
```

### Example 3: Dark Mode Variant

```python
theme = EventTheme.objects.get(event=event)
theme.color_mode = 'dark'
theme.save()

# Frontend automatically switches to dark mode tokens
```

### Example 4: Custom CSS

```python
theme = EventTheme.objects.get(event=event)
theme.custom_css = """
.event-header {
  background: linear-gradient(135deg, var(--color-primary), var(--color-secondary));
  padding: var(--spacing-8);
}
"""
theme.save()
```

## Dark Mode Implementation

### Automatic Dark Mode

The system automatically provides dark mode variants:

```json
{
  "colors": {
    "surface": "#FFFFFF",
    "text": "#111827"
  },
  "darkMode": {
    "colors": {
      "surface": "#1F1F1F",
      "text": "#F5F5F5"
    }
  }
}
```

### User Controls

```html
<!-- Light/Dark/Auto mode selector -->
<button id="theme-toggle" data-mode="light">
  <i class="icon-sun"></i>
</button>
```

### CSS Implementation

```css
/* Light mode (default) */
:root {
  --color-surface: #FFFFFF;
  --color-text: #111827;
}

/* Dark mode */
[data-theme="dark"] {
  --color-surface: #1F1F1F;
  --color-text: #F5F5F5;
}
```

## Accessibility Considerations

### Color Contrast

All color pairs maintain WCAG AA minimum contrast ratios:

- Text on surface: 4.5:1 (normal), 3:1 (large)
- Semantic colors have light/dark variants for visibility

### Token Validation

Override validation ensures:

- Valid hex color format
- Minimum contrast ratios on semantic pairs
- Valid CSS values for all properties
- No missing critical tokens

## Performance Optimization

### Token Caching

- Base tokens loaded once at startup
- Merged tokens cached per scope (org/event)
- Cache invalidated on token updates

### CSS Variable Efficiency

- Single `:root` scope for base tokens
- Minimal specificity for overrides
- No per-component inline styles

### Runtime Switching

- Theme updates without page reload
- Only CSS variables changed, no DOM manipulation
- ~10ms update time for complete theme swap

## Testing

### Test Coverage

```python
# test_theme_loader.py
def test_token_merging():
    base = ThemeTokenLoader.load_base_tokens()
    overrides = {'colors': {'primary': '#FF0000'}}
    merged = ThemeTokenLoader.merge_tokens(base, overrides)
    assert merged['colors']['primary'] == '#FF0000'

def test_dark_mode_tokens():
    tokens = ThemeTokenLoader.load_base_tokens()
    assert 'darkMode' in tokens
    assert tokens['darkMode']['colors']['surface'] != tokens['colors']['surface']
```

### Frontend Tests

```typescript
// theme.test.ts
describe('Theme Manager', () => {
  it('should update tokens at runtime', () => {
    themeManager.updateToken('colors.primary', '#FF0000');
    expect(themeManager.getToken('colors.primary')).toBe('#FF0000');
  });

  it('should toggle dark mode', () => {
    themeManager.setColorMode('dark');
    expect(themeManager.isDarkMode()).toBe(true);
  });
});
```

## Migration Guide

### From Hardcoded Styles

**Before:**
```css
.button { background-color: #EB2188; }
```

**After:**
```css
.button { background-color: var(--color-primary); }
```

### Updating Components

1. Replace hardcoded color values with token references
2. Update typography sizes to use token variables
3. Use spacing tokens for padding/margin
4. Apply border-radius tokens
5. Reference shadow tokens

## Future Enhancements

- Theme Editor UI with visual builder
- Preset theme library
- Theme sharing/marketplace
- Advanced color generation (complementary, analogous)
- Layout token system
- Animation/transition tokens
- Internationalization per token

## Troubleshooting

### Tokens Not Updating

1. Check browser DevTools - CSS variables should update
2. Verify dark mode CSS variables are loaded
3. Clear browser cache and localStorage
4. Check network request for theme endpoint

### Color Contrast Issues

1. Use provided validation schema
2. Test with WCAG contrast checker
3. Use light/dark variants for semantic colors
4. Document any intentional deviations

### Performance Issues

1. Minimize token-specific CSS selectors
2. Avoid per-component inline styles
3. Cache merged tokens on server
4. Use CSS variables instead of SCSS variables at runtime

---

For questions or contributions, please refer to the main Eventyay documentation.
