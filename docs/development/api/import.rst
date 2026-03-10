.. highlight:: python
   :linenothreshold: 5

.. _`importcol`:

Extending the order import process
==================================

It's possible through the backend to import orders into eventyay, for example from a legacy ticketing system. If your
plugins defines additional data structures around orders, it might be useful to make it possible to import them as well.

Import process
--------------

Here's a short description of eventyay' import process to show you where the system will need to interact with your plugin.
You can find more detailed descriptions of the attributes and methods further below.

1. The user uploads a CSV file. The system tries to parse the CSV file and understand its column headers.

2. A preview of the file is shown to the user and the user is asked to assign the various different input parameters to
   columns of the file or static values. For example, the user either needs to manually select a product or specify a
   column that contains a product. For this purpose, a select field is rendered for every possible input column,
   allowing the user to choose between a default/empty value (defined by your ``default_value``/``default_label``)
   attributes, the columns of the uploaded file, or a static value (defined by your ``static_choices`` method).

3. The user submits its assignment and the system uses the ``resolve`` method of all columns to get the raw value for
   all columns.

4. The system uses the ``clean`` method of all columns to verify that all input fields are valid and transformed to the
   correct data type.

5. The system prepares internal model objects (``Order`` etc) and uses the ``assign`` method of all columns to assign
   these objects with actual values.

6. The system saves all of these model objects to the database in a database transaction. Plugins can create additional
   objects in this stage through their ``save`` method.

Column registration
-------------------

The import API does not make a lot of usage from signals, however, it
does use a signal to get a list of all available import columns. Your plugin
should listen for this signal and return the subclass of ``eventyay.base.orderimport.ImportColumn``
that we'll provide in this plugin:

.. sourcecode:: python

    from django.dispatch import receiver

    from eventyay.base.signals import order_import_columns


    @receiver(order_import_columns, dispatch_uid="custom_columns")
    def register_column(sender, **kwargs):
        return [
            EmailColumn(sender),
        ]

The column class API
--------------------

.. class:: eventyay.base.orderimport.ImportColumn

   The central object of each import extension is the subclass of ``ImportColumn``.

   .. py:attribute:: ImportColumn.event

      The default constructor sets this property to the event we are currently
      working for.

   .. py:attribute:: identifier

      Unique, internal name of the column.

      This is an abstract attribute, you **must** override this!

   .. py:attribute:: verbose_name

      Human-readable description of the column.

      This is an abstract attribute, you **must** override this!

   .. py:attribute:: default_value

      Internal default value for the assignment of this column. Defaults to ``empty``.
      Return ``None`` to disable this option.

   .. py:attribute:: default_label

      Human-readable description of the default assignment of this column, defaults to "Keep empty".

   .. py:attribute:: initial

      Initial value for the form component.

   .. py:method:: static_choices()

      This will be called when rendering the form component and allows you to return a list of values
      that can be selected by the user statically during import.

      :return: list of 2-tuples of strings

   .. py:method:: resolve(settings, record)

      This method will be called to get the raw value for this field, usually by either using a static
      value or inspecting the CSV file for the assigned header.

   .. py:method:: clean(value, previous_values)

      Allows you to validate the raw input value for your column. Raise ``ValidationError`` if the
      value is invalid.

      :param value: The raw value of your column as returned by ``resolve``.
      :param previous_values: Dictionary containing the validated values of all columns that have
                              already been validated.

   .. py:method:: assign(value, order, position, invoice_address, **kwargs)

      This will be called to perform the actual import. Set attributes on the ``order``, ``position``,
      or ``invoice_address`` objects based on the input ``value``.

   .. py:method:: save(order)

      This will be called to perform the actual import inside the database transaction. The input
      object ``order`` has already been saved to the database.

Example
-------

For example, the import column responsible for assigning email addresses looks like this:

.. sourcecode:: python

   class EmailColumn(ImportColumn):
       identifier = 'email'
       verbose_name = _('E-mail address')

       def clean(self, value, previous_values):
           if value:
               EmailValidator()(value)
           return value

       def assign(self, value, order, position, invoice_address, **kwargs):
           order.email = value
