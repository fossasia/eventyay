.. highlight:: python
   :linenothreshold: 5

Writing an HTML e-mail renderer plugin
======================================

An email renderer class controls how the HTML part of e-mails sent by Eventyay is built.
The creation of such a plugin is very similar to creating an export output.

Please read :ref:`Creating a plugin <pluginsetup>` first, if you haven't already.

Output registration
-------------------

The email HTML renderer API does not make a lot of usage from signals, however, it
does use a signal to get a list of all available email renderers. Your plugin
should listen for this signal and return the subclass of ``eventyay.base.email.BaseHTMLMailRenderer``
that we'll provide in this plugin:

.. code-block:: python

    from django.dispatch import receiver

    from eventyay.base.signals import register_html_mail_renderers


    @receiver(register_html_mail_renderers, dispatch_uid="renderer_custom")
    def register_mail_renderers(sender, **kwargs):
        from .email import MyMailRenderer
        return MyMailRenderer


The renderer class
------------------

.. class:: eventyay.base.email.BaseHTMLMailRenderer

   The central object of each email renderer is the subclass of ``BaseHTMLMailRenderer``.

   .. py:attribute:: BaseHTMLMailRenderer.event

      The default constructor sets this property to the event we are currently
      working for.

   .. py:attribute:: identifier

      A short and unique identifier for this renderer. This should only contain lowercase letters
      and in most cases will be the same as your package name.

      This is an abstract attribute, you **must** override this!

   .. py:attribute:: verbose_name

      A human-readable name for this renderer. This should be short but self-explanatory.

      This is an abstract attribute, you **must** override this!

   .. py:attribute:: thumbnail_filename

      The filename of a thumbnail image for this renderer.

      This is an abstract attribute, you **must** override this!

   .. py:attribute:: is_available

      Whether this renderer is available for the current event.

   .. py:method:: render(plain_body, plain_signature, subject, order=None, position=None)

      This method should generate the HTML part of the email.

      :param plain_body: The body of the email in plain text.
      :param plain_signature: The signature with event organizer contact details in plain text.
      :param subject: The email subject.
      :param order: The order if this email is connected to one, otherwise ``None``.
      :param position: The order position if this email is connected to one, otherwise ``None``.
      :return: An HTML string

      This is an abstract method, you **must** implement this!

Helper class for template-base renderers
----------------------------------------

The email renderer that ships with Eventyay is based on Django templates to generate HTML.
In case you also want to render emails based on a template, we provided a ready-made base
class ``TemplateBasedMailRenderer`` that you can re-use to perform the following steps:

* Convert the body text and the signature to HTML using our markdown renderer

* Render the template

* Call `inlinestyler`_ to convert all ``<style>`` style sheets to inline ``style=""``
  attributes for better compatibility

To use it, you just need to implement some variables:

.. code-block:: python

    class ClassicMailRenderer(TemplateBasedMailRenderer):
        verbose_name = _('Eventyay default')
        identifier = 'classic'
        thumbnail_filename = 'eventyaybase/email/thumb.png'
        template_name = 'eventyaybase/email/plainwrapper.html'

The template is passed the following context variables:

``site``
   Name of the eventyay tickets installation (``settings.INSTANCE_NAME``)

``site_url``
   Root URL of the eventyay tickets installation (``settings.SITE_URL``)

``body``
   The body as markdown (render with ``{{ body|safe }}``)

``subject``
   The email subject

``color``
   The primary color of the event

``event``
   The ``Event`` object

``signature`` (optional, only if configured)
   The signature with event organizer contact details as markdown (render with ``{{ signature|safe }}``)

``order`` (optional, only if applicable)
   The ``Order`` object

``position`` (optional, only if applicable)
   The ``OrderPosition`` object

.. _inlinestyler: https://pypi.org/project/inlinestyler/
