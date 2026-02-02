# Eventyay Theme Token Specification

## Overview
This document defines the official design token system for Eventyay.  
All visual styling must reference tokens instead of hardcoded values.

Token hierarchy:
Foundation → Semantic → Component

This hierarchy ensures:
- Foundation tokens define raw design values
- Semantic tokens express UI meaning
- Component tokens customize complex components without breaking consistency

---

## 1. Foundation Tokens

Foundation tokens define raw design values and must never reference UI components or other tokens.

### Categories
- Colors: `--color-*`
- Fonts: `--font-*`
- Spacing: `--space-*`
- Radii: `--radius-*`
- Borders: `--border-*`
- Shadows: `--shadow-*`

### Naming Rules
- Must be lowercase
- Must use hyphen-separated names
- Must not reference other tokens
- Must represent a single design value

### Examples
```css
--color-primary
--color-secondary
--color-surface
--color-background
--color-text
--color-success
--color-warning
--color-error

--font-body
--font-heading
--font-mono

--space-xs
--space-sm
--space-md
--space-lg
--space-xl

--radius-sm
--radius-md
--radius-lg

--border-width-sm
--border-width-md

--shadow-sm
--shadow-md
--shadow-lg

---

## 2. Semantic Tokens

Semantic tokens describe UI meaning and must map to foundation tokens.  
Components MUST use semantic tokens instead of foundation tokens.

### Format
```

--semantic-<domain>-<property>

````

### Examples
```css
--semantic-button-bg
--semantic-button-text
--semantic-header-bg
--semantic-header-text
--semantic-card-surface
--semantic-link-text
--semantic-link-hover
````

### Mapping Rule

Each semantic token must reference a foundation token.

Example:

```css
--semantic-button-bg: var(--color-primary);
--semantic-header-text: var(--color-text);
```

---

## 3. Component Tokens

Component tokens are optional and used only for complex or highly customized components.

### Format

```
--component-<component>-<part>-<property>
```

### Examples

```css
--component-navbar-bg
--component-navbar-link-text
--component-modal-radius
```

### Usage Rule

Component tokens must reference semantic tokens, not foundation tokens.

Example:

```css
--component-navbar-bg: var(--semantic-header-bg);
```

---

## 4. State Modifiers

State modifiers may be appended to semantic or component tokens.

### Allowed States

* `-hover`
* `-active`
* `-focus`
* `-disabled`
* `-selected`

### Examples

```css
--semantic-button-bg-hover
--semantic-input-border-focus
--component-navbar-link-active
```

---

## 5. Override Priority

Theme resolution order:

1. Base Theme
2. Organization Overrides
3. Event Overrides
4. User Preference (Light/Dark)

The last applied value always takes precedence.

---

## 6. Validation Rules

All tokens must follow these constraints:

* Token names must be lowercase
* Tokens must use hyphen-separated naming
* No spaces or underscores allowed
* Foundation tokens must not reference other tokens
* Semantic tokens must reference foundation tokens
* Component tokens must reference semantic tokens

---

## 7. Versioning

Themes must declare a version to ensure forward compatibility.

Example:

```json
{
  "themeVersion": "1.0.0",
  "tokens": {
    "color": {
      "primary": "#EB2188"
    }
  }
}
```

Breaking changes to token structure require a major version bump.

---

## 8. Accessibility Requirements

* Text color tokens must meet WCAG AA contrast ratio (4.5:1 minimum)
* Focus state tokens must be defined for interactive components
* Error, warning, and success tokens must be visually distinguishable

---

## 9. Example Token Flow

Foundation:

```css
--color-primary: #EB2188;
--color-text: #111827;
```

Semantic:

```css
--semantic-button-bg: var(--color-primary);
--semantic-button-text: var(--color-text);
```

Component:

```css
--component-navbar-bg: var(--semantic-header-bg);
```

Component usage:

```css
.navbar {
  background: var(--component-navbar-bg);
}
```

---

## 10. Enforcement

All new shared UI components must:

* Use semantic or component tokens
* Avoid hardcoded CSS values
* Declare new tokens in the theme schema and documentation

