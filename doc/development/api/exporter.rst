.. highlight:: python
   :linenothreshold: 5

Writing an exporter plugin
==========================

An Exporter is a method to export the product and order data in Eventyay for later use in another
program.

In this document, we will walk through the creation of an exporter output plugin step by step.

Please read :ref:`Creating a plugin <pluginsetup>` first, if you haven't already.

Exporter registration
---------------------

The exporter API does not make a lot of usage from signals, however, it does use a signal to get a list of
all available exporters. Your plugin should listen for this signal and return the subclass of
``eventyay.base.exporter.BaseExporter``
that we'll provide in this plugin:

.. code-block:: python

    from django.dispatch import receiver

    from eventyay.base.signals import register_data_exporters


    @receiver(register_data_exporters, dispatch_uid="exporter_myexporter")
    def register_data_exporter(sender, **kwargs):
        from .exporter import MyExporter
        return MyExporter

Some exporters might also prove to be useful, when provided on an organizer-level. In order to declare your
exporter as capable of providing exports spanning multiple events, your plugin should listen for this signal
and return the subclass of ``eventyay.base.exporter.BaseExporter`` that we'll provide in this plugin:

.. code-block:: python

    from django.dispatch import receiver

    from eventyay.base.signals import register_multievent_data_exporters


    @receiver(register_multievent_data_exporters, dispatch_uid="multieventexporter_myexporter")
    def register_multievent_data_exporter(sender, **kwargs):
        from .exporter import MyExporter
        return MyExporter

If your exporter supports both event-level and multi-event level exports, you will need to listen for both
signals.

The exporter class
------------------

.. class:: eventyay.base.exporter.BaseExporter

   The central object of each exporter is the subclass of ``BaseExporter``.

   .. py:attribute:: BaseExporter.event

      The default constructor sets this property to the event we are currently
      working for.

   .. py:attribute:: identifier

      A short and unique identifier for this exporter. This should only contain lowercase letters
      and in most cases will be the same as your package name.

      This is an abstract attribute, you **must** override this!

   .. py:attribute:: verbose_name

      A human-readable name for this exporter. This should be short but self-explaining.
      Good examples include 'JSON' or 'Microsoft Excel'.

      This is an abstract attribute, you **must** override this!

   .. py:attribute:: export_form_fields

      When the event's administrator visits the export page, this property is called to return
      the configuration fields available. It should return a dictionary where the keys are field
      names and the values are corresponding Django form fields.

   .. py:method:: render(form_data)

      Render the exported file and return a tuple consisting of a filename, a file type
      and file content.

      :param form_data: The form data of the export details form
      :return: A tuple of (filename, content_type, file_content)

      This is an abstract method, you **must** override this!
