.. highlight:: python
   :linenothreshold: 5

Writing a ticket output plugin
==============================

A ticket output is a method to offer a ticket (an order) for the user to download.

In this document, we will walk through the creation of a ticket output plugin. This
is very similar to creating an export output.

Please read :ref:`Creating a plugin <pluginsetup>` first, if you haven't already.

Output registration
-------------------

The ticket output API does not make a lot of usage from signals, however, it
does use a signal to get a list of all available ticket outputs. Your plugin
should listen for this signal and return the subclass of ``eventyay.base.ticketoutput.BaseTicketOutput``
that we'll provide in this plugin:

.. code-block:: python

    from django.dispatch import receiver

    from eventyay.base.signals import register_ticket_outputs


    @receiver(register_ticket_outputs, dispatch_uid="output_pdf")
    def register_ticket_output(sender, **kwargs):
        from .ticketoutput import PdfTicketOutput
        return PdfTicketOutput


The output class
----------------

.. class:: eventyay.base.ticketoutput.BaseTicketOutput

   The central object of each ticket output is the subclass of ``BaseTicketOutput``.

   .. py:attribute:: BaseTicketOutput.event

      The default constructor sets this property to the event we are currently
      working for.

   .. py:attribute:: BaseTicketOutput.settings

      The default constructor sets this property to a ``SettingsSandbox`` object. You can
      use this object to store settings using its ``get`` and ``set`` methods. All settings
      you store are transparently prefixed, so you get your very own settings namespace.

   .. py:attribute:: identifier

      A short and unique identifier for this ticket output.

      This is an abstract attribute, you **must** override this!

   .. py:attribute:: verbose_name

      A human-readable name for this ticket output.

      This is an abstract attribute, you **must** override this!

   .. py:attribute:: is_enabled

      Whether this ticket output is enabled.

   .. py:attribute:: multi_download_enabled

      Whether downloading multiple tickets at once is enabled.

   .. py:attribute:: settings_form_fields

      A dictionary of form fields for the ticket output settings.

   .. py:method:: settings_content_render(request)

      Render additional content for the settings page.

   .. py:method:: generate(position)

      Generate a ticket for a single order position.

      :param position: The order position to generate a ticket for.
      :return: A tuple of (filename, content_type, file_content)

   .. py:method:: generate_order(order)

      Generate tickets for all positions in an order.

      :param order: The order to generate tickets for.
      :return: A tuple of (filename, content_type, file_content)

   .. py:attribute:: download_button_text

      The text for the download button.

   .. py:attribute:: download_button_icon

      The icon for the download button.

   .. py:attribute:: multi_download_button_text

      The text for the multi-download button.

   .. py:attribute:: long_download_button_text

      The long text for the download button.

   .. py:attribute:: preview_allowed

      Whether previewing tickets is allowed.

   .. py:attribute:: javascript_required

      Whether JavaScript is required to use this ticket output.
