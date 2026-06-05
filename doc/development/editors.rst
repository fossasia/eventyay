Rich Text and Email Editors
===========================

This page documents which editor implementation is used in each area of
eventyay, how they are integrated, and how to reuse the shared Tiptap layer
in new forms.

Overview
--------

eventyay uses three editor implementations:

.. list-table::
   :header-rows: 1
   :widths: 30 25 45

   * - Area
     - Editor
     - Notes
   * - Talk submission forms (abstract, description, notes)
     - Toast UI Editor (Markdown)
     - Stays as-is. Fields use ``MarkdownWidget`` / ``I18nMarkdownTextarea``.
   * - Video rich text and chat
     - Quill 2 (Vue component)
     - Stays as-is. Implemented in ``webapp/video/``.
   * - Ticket forms / general rich text
     - **Tiptap** (``RichTextField``)
     - New. Use for new plain-HTML rich text fields.
   * - Email body editing
     - **Tiptap** (``EmailBodyField``)
     - New. Gmail-like editor with placeholder insertion.


Tiptap Editor Layer
-------------------

The shared Tiptap implementation lives in two places:

* **Frontend bundle**: ``app/eventyay/webapp/editor/``
* **Django layer**: ``app/eventyay/common/``

Frontend Bundle (``webapp/editor/``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A Vite-built IIFE bundle with no external framework dependency.  Built output
goes to ``eventyay/data/compiled-frontend/editor/`` (``editor.js`` +
``editor.css``).

**Key files:**

.. code-block:: text

   webapp/editor/
     src/
       index.js                      # Entry point; auto-mounts on [data-tiptap-profile]
       profiles/
         richtext.js                 # Simple rich text (Bold, Italic, Underline, Lists, Link)
         email.js                    # Email profile (extends richtext + placeholder chips)
       extensions/
         placeholder-variable.js    # Custom non-editable inline node for {{ var }} chips
       toolbar.js                    # Toolbar DOM builder
       styles.css                    # Editor and toolbar styles

**Editor profiles:**

``richtext``
  For general-purpose rich text fields.  Toolbar: Bold, Italic, Underline,
  Bullet list, Numbered list, Link, Clear formatting, Undo, Redo.

``email``
  Extends ``richtext`` with an "Insert placeholder" dropdown (populated from
  ``data-tiptap-placeholders`` JSON on the textarea) and a Preview button
  (calls ``data-tiptap-preview-url``).

**Progressive enhancement:**

The bundle mounts on any ``<textarea data-tiptap-profile="...">`` it finds at
load time.  On form submit, it syncs the editor HTML back into the hidden
textarea so the Django form receives the HTML value.  When JavaScript is
disabled the original textarea is used directly.

**Building:**

The bundle is built as part of ``make npminstall`` in ``app/``:

.. code-block:: bash

   npm ci --prefix=eventyay/webapp/editor
   OUT_DIR=$(pwd)/eventyay/data/compiled-frontend/ npm run build --prefix=eventyay/webapp/editor

Lazy Loader (``static/common/js/tiptapLoader.js``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A tiny script included in all base templates.  It checks for
``[data-tiptap-profile]`` elements on the current page and, if found,
dynamically injects ``editor.js`` and ``editor.css``.  Pages without Tiptap
fields incur no bundle download.

The loader is inserted via a ``<script>`` tag with ``data-tiptap-js`` and
``data-tiptap-css`` data attributes pointing to the compiled bundle URLs.  This
mirrors the pattern used by ``toastuiLoader.js``.


Django Integration
------------------

Widgets
~~~~~~~

Both widgets are in ``eventyay.common.forms.widgets``.

``RichTextWidget``
  Extends ``Textarea``.  Sets ``data-tiptap-profile="richtext"`` on the
  textarea.  Uses template ``common/widgets/richtext.html`` which wraps the
  textarea in ``<div data-tiptap-wrapper>``.

``EmailEditorWidget``
  Extends ``Textarea``.  Sets ``data-tiptap-profile="email"``.  Accepts
  ``placeholders`` (list of variable names) and ``preview_url`` (AJAX endpoint
  URL).  Uses template ``common/widgets/email_editor.html``.

Form Fields
~~~~~~~~~~~

Both fields are in ``eventyay.common.forms.fields``.

``RichTextField``
  A ``CharField`` that uses ``RichTextWidget`` and calls
  ``sanitize_rich_text()`` inside ``clean()``.

``EmailBodyField``
  A ``CharField`` that uses ``EmailEditorWidget`` and calls
  ``sanitize_email_html()`` inside ``clean()``.  Constructor accepts
  ``placeholders`` and ``preview_url``.

Example usage::

   from eventyay.common.forms.fields import RichTextField, EmailBodyField

   class MyForm(forms.Form):
       description = RichTextField(label='Description')
       message = EmailBodyField(
           label='Message',
           placeholders=['attendee_name', 'event_name', 'order_code'],
           preview_url='/control/.../editor/email-preview',
       )

Server-side Sanitization
~~~~~~~~~~~~~~~~~~~~~~~~

``eventyay.common.sanitizers`` provides two functions backed by the ``nh3``
library (Rust/Ammonia-based):

``sanitize_rich_text(html)``
  Allowed tags: ``p``, ``br``, ``strong``, ``b``, ``em``, ``i``, ``u``,
  ``ul``, ``ol``, ``li``, ``a``, ``blockquote``.
  Allowed link attributes: ``href``, ``title`` (``http://`` / ``https://`` only).
  Adds ``rel="noopener noreferrer"`` to all anchor elements.

``sanitize_email_html(html)``
  Same as ``sanitize_rich_text`` plus ``span``.  Does **not** inject
  ``rel`` attributes because email clients may display or strip them.

All unsafe tags, event attributes (``onclick``, ``onerror``, etc.), and
non-HTTP/HTTPS link protocols are removed.

Email Preview Endpoint
~~~~~~~~~~~~~~~~~~~~~~

``POST /control/<organizer>/<event>/editor/email-preview``

Accepts a JSON body ``{ "html": "<p>...</p>" }``, sanitizes it with
``sanitize_email_html``, and returns ``{ "html": "<p>...</p>" }``.

Requires ``can_change_orders`` permission on the event.  The editor's Preview
button calls this URL and displays the result in a ``<dialog>`` modal.

URL name: ``control:event.editor.email.preview``


Placeholder Variables
---------------------

The email profile supports ``{{ variable_name }}`` placeholder chips.  Each
chip is a non-editable inline Tiptap node that serialises as literal
``{{ variable_name }}`` text in the stored HTML.

Placeholders for an email form should be derived from the same source used by
the existing email system (``get_available_placeholders`` from
``eventyay.base.email``).  Pass the plain variable names (without braces) to
``EmailBodyField(placeholders=[...])``::

   from eventyay.base.email import get_available_placeholders

   placeholder_names = sorted(
       get_available_placeholders(event, ['event', 'order']).keys()
   )
   field = EmailBodyField(placeholders=placeholder_names, ...)


Toast UI Markdown Editor (existing)
------------------------------------

Talk submission fields (abstract, description, notes, biography) continue to
use ``MarkdownWidget`` / ``I18nMarkdownTextarea`` backed by the vendored Toast
UI Editor bundle in ``static/vendored/toastui-editor/``.

These fields store **Markdown**, not HTML.  Migration to Tiptap (with Markdown
serialisation) may be evaluated in a future iteration but is explicitly out of
scope for this implementation.

``MarkdownWidget`` is in ``eventyay.common.forms.widgets``.
``I18nMarkdownTextarea`` is in ``eventyay.base.forms``.


Quill (existing, video only)
-----------------------------

``webapp/video/`` uses Quill 2 for exhibitor/poster rich text and the chat
input.  Quill is an npm dependency of the video app only and is not shared
with the rest of eventyay.  Migration to Tiptap is a future task.

There is also a legacy vendored copy of Quill 1.1.9 in
``static/pages/`` which appears to be unused by current templates.


Migration Path
--------------

The long-term goal is for Tiptap to be the single shared editor framework:

1. **New rich text fields** → use ``RichTextField`` / ``EmailBodyField`` now.
2. **Toast UI** (Talk submissions) → evaluate migration to Tiptap with
   Markdown serialisation in a future iteration.
3. **Quill** (video app) → evaluate migration to Tiptap Vue component in a
   future iteration.

Do **not** introduce CKEditor, TinyMCE, ProseMirror directly, or any other
editor framework into new code.
