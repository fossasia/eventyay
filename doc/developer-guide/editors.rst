Rich Text and Email Editors
===========================

This page documents which editor implementation is used in each area of
eventyay, how they are integrated, and how to reuse the shared Tiptap layer
in new forms.

Overview
--------

eventyay currently uses three editor implementations. This is a current
implementation reference, not a user-facing Markdown editor tutorial:

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
   * - Ticket Message center (compose / outbox / team mail)
     - **Tiptap** (``I18nEmailBodyFormField``)
     - Primary integration. Gmail-like editor with placeholder insertion.
   * - Order personal email (order detail → Send email)
     - **Tiptap** (``EmailBodyField``)
     - Secondary. Same email profile for one-off messages.


Tiptap Editor Layer
-------------------

The shared Tiptap implementation lives in two places:

* **Frontend bundle**: ``app/eventyay/webapp/editor/``
* **Django layer**: ``app/eventyay/common/``

Frontend Bundle (``webapp/editor/``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A Vite-built IIFE bundle with no external framework dependency.  The built
``editor.js`` and ``editor.css`` are committed under ``eventyay/static/editor/``
(same pattern as Toast UI in ``static/vendored/``) so production
``collectstatic`` picks them up without an extra Docker npm build.

**Key files:**

.. code-block:: text

   webapp/editor/                    # Source (edit here)
     src/
       index.js                      # Entry point; auto-mounts on [data-tiptap-profile]
       profiles/
         richtext.js                 # Simple rich text (Bold, Italic, Underline, Lists, Link)
         email.js                    # Email profile (extends richtext + placeholder chips)
       extensions/
         placeholder-variable.js    # Custom non-editable inline node for {var} chips
       toolbar.js                    # Toolbar DOM builder
       styles.css                    # Editor and toolbar styles

   eventyay/static/editor/           # Deployed bundle (commit after rebuilding)
     editor.js
     editor.css

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

After changing ``webapp/editor/`` source, rebuild and commit the output under
``static/editor/``:

.. code-block:: bash

   npm ci --prefix=eventyay/webapp/editor
   OUT_DIR=$(pwd)/eventyay/static/ npm run build --prefix=eventyay/webapp/editor

``make npminstall`` in ``app/`` runs the same editor build step.

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

``I18nEmailEditorWidget`` / ``I18nEmailBodyFormField``
  For multi-locale email bodies (Message center).  Extends django-i18nfield's
  ``I18nTextarea`` / ``I18nFormField``.  Each locale tab gets its own Tiptap
  email editor instance.  Sanitizes every locale value in ``clean()``.

Message Center (primary wiring)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The **Message center** plugin (``eventyay.plugins.sendmail``) is the main
production use case for the Tiptap email editor in Tickets:

* **Compose** — mass mail to orders/attendees (``MailForm``)
* **Outbox** — edit queued messages before sending (``EmailQueueEditForm``)
* **Compose to teams** — internal team notifications (``TeamMailForm``)

All three forms use ``I18nEmailBodyFormField`` for the **Message** field.  The
editor toolbar provides formatting, placeholder insertion, and an AJAX preview
via ``control:event.editor.email.preview``.

Plain-text and Markdown bodies stored before this change continue to work:
``compile_email_body()`` in ``eventyay.base.templatetags.rich_text`` detects
whether content is already HTML and only runs ``markdown_compile_email()`` for
legacy plain-text bodies.

Example usage (single-locale form)::

   from eventyay.common.forms.fields import RichTextField, EmailBodyField

   class MyForm(forms.Form):
       description = RichTextField(label='Description')
       message = EmailBodyField(
           label='Message',
           placeholders=['attendee_name', 'event_name', 'order_code'],
           preview_url='/control/.../editor/email-preview',
       )

Example usage (Message center, multi-locale)::

   from eventyay.common.forms.fields import I18nEmailBodyFormField
   from eventyay.common.forms.widgets import I18nEmailEditorWidget

   self.fields['message'] = I18nEmailBodyFormField(
       label='Message',
       widget=I18nEmailEditorWidget,
       widget_kwargs={'placeholders': placeholder_names, 'preview_url': preview_url},
       locales=event.settings.get('locales'),
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


Tab-based Edit/Preview (``static/common/js/richtextPreview.js``)
------------------------------------------------------------------

The toolbar's built-in Preview button (see above) opens a popup ``<dialog>``.
Some areas instead render an "Edit" / "Preview" tab pair next to the field
(e.g. the Talks/CfP Call for Team Members description, custom email
templates) so the preview stays visible alongside the editor rather than in a
modal.

``static/common/js/richtextPreview.js`` implements this tab-based behaviour
once, in core, so plugins do not need to ship their own copy. It is loaded on
every ``control``, ``orga``, and ``eventyay_common`` page (same pattern as
``dropdown.js``) and activates purely through data attributes — no Python or
JS wiring is required beyond adding the markup.

**Rich text preview** (single field, single locale):

.. code-block:: html

   <div data-richtext-preview-wrapper data-richtext-preview-url="{% url 'myapp:description_preview' %}">
     <ul class="nav nav-tabs" role="tablist">
       <li role="presentation" class="active">
         <a data-toggle="tab" href="#description_edit">Edit</a>
       </li>
       <li role="presentation">
         <a data-toggle="tab" href="#description_preview" data-richtext-preview-tab>Preview</a>
       </li>
     </ul>
     <div class="tab-content">
       <div id="description_edit" class="tab-pane fade in active">
         {% bootstrap_field form.description show_label=False form_group_class="" %}
       </div>
       <div id="description_preview" class="tab-pane">
         <div class="richtext-preview"></div>
       </div>
     </div>
   </div>

Clicking the Preview tab POSTs the current textarea value as ``content`` to
``data-richtext-preview-url`` and expects a JSON response
``{ "html": "<p>...</p>" }``, which replaces the contents of
``.richtext-preview``.

**Email preview** (multi-locale, one textarea per language):

.. code-block:: html

   <div data-email-preview-wrapper data-email-preview-url="{% url 'myapp:email_preview' %}">
     ...
     <a data-toggle="tab" href="#message_preview" data-email-preview-tab>Preview</a>
     ...
     <div id="message_preview" class="tab-pane">
       <div class="mail-preview-group">
         {% for locale in event.settings.locales %}
           <div lang="{{ locale }}" class="mail-preview"></div>
         {% endfor %}
       </div>
     </div>
   </div>

Clicking the Preview tab POSTs one ``body_<locale>`` field per ``<textarea
lang="...">`` found inside the wrapper and expects
``{ "previews": { "en": "<p>...</p>", "de": "<p>...</p>" } }``, which fills
each ``.mail-preview[lang=...]`` block.

Both variants require a plugin-supplied backend view, since the preview
content (available placeholders, sample values, permission checks) is
context-specific. The JS layer only handles the AJAX round-trip and DOM
update; it does not assume a specific view class.

This mechanism is independent from the toolbar preview button
(``data-tiptap-preview-url`` / ``control:event.editor.email.preview``) and can
be used with plain textareas as well — Tiptap enhancement is optional.


Placeholder Variables
---------------------

The email profile supports ``{variable_name}`` placeholder chips.  Each
chip is a non-editable inline Tiptap node that serialises as literal
``{variable_name}`` text in the stored HTML.

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

``webapp/video/`` uses Quill 2 for the chat
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
