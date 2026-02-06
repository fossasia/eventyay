---
applyTo: "app/eventyay/**/templates/**/*.html"
---

# Django Template Instructions

## Quotes

- Use different quote styles when nesting. For example, do:

  ```django
  <a href="{% url 'eventyay_common:account.email' %}">
  ```

  do not:
  
  ```django
  <a href="{% url "eventyay_common:account.email" %}">
  ```

  because the latter one makes syntax highlighting go crazy and is difficult to review.

- Prefer single quotes because they require fewer keystrokes and are less visually busy.

- Newly created files should use 2-space indentation (does not apply to editing old files).

## Business code

- Don't do complex code in templates because it is difficult to review; move it to Python files.

- Avoid complex code (like `if` chains) inside HTML attributes (like inside `href` of `<a>` elements),
because that code cannot be highlighted and is difficult to review.
