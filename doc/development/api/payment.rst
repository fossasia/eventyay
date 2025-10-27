.. highlight:: python
   :linenothreshold: 5

Writing a payment provider plugin
=================================

In this document, we will walk through the creation of a payment provider plugin. This
is very similar to creating an export output.

Please read :ref:`Creating a plugin <pluginsetup>` first, if you haven't already.

.. warning:: We changed our payment provider API a lot in Eventyay 2.x. Our documentation page on :ref:`payment2.0`
             might be insightful even if you do not have a payment provider to port, as it outlines the rationale
             behind the current design.

Provider registration
---------------------

The payment provider API does not make a lot of usage from signals, however, it
does use a signal to get a list of all available payment providers. Your plugin
should listen for this signal and return the subclass of ``eventyay.base.payment.BasePaymentProvider``
that the plugin will provide:

.. code-block:: python

    from django.dispatch import receiver

    from eventyay.base.signals import register_payment_providers


    @receiver(register_payment_providers, dispatch_uid="payment_paypal")
    def register_payment_provider(sender, **kwargs):
        from .payment import Paypal
        return Paypal


The provider class
------------------

.. py:class:: eventyay.base.payment.BasePaymentProvider

   The central object of each payment provider is the subclass of ``BasePaymentProvider``.

   .. py:attribute:: BasePaymentProvider.event

      The default constructor sets this property to the event we are currently
      working for.

   .. py:attribute:: BasePaymentProvider.settings

      The default constructor sets this property to a ``SettingsSandbox`` object. You can
      use this object to store settings using its ``get`` and ``set`` methods. All settings
      you store are transparently prefixed, so you get your very own settings namespace.

   .. py:attribute:: identifier

      A short and unique identifier for this payment provider.

      This is an abstract attribute, you **must** override this!

   .. py:attribute:: verbose_name

      A human-readable name for this payment provider.

      This is an abstract attribute, you **must** override this!

   .. py:attribute:: public_name

      The public name of this payment provider as shown to customers.

   .. py:attribute:: is_enabled

      Whether this payment provider is enabled.

   .. py:attribute:: priority

      The priority of this payment provider. Lower values are shown first.

   .. py:attribute:: settings_form_fields

      A dictionary of form fields for the provider settings.

   .. py:method:: settings_form_clean(cleaned_data)

      Validate the settings form data.

   .. py:method:: settings_content_render(request)

      Render additional content for the settings page.

   .. py:method:: is_allowed(request, total=None)

      Check if this payment provider is allowed for the given request.

   .. py:method:: payment_form_render(request)

      Render the payment form shown during checkout.

   .. py:method:: payment_form(request)

      Return a form instance for payment details.

   .. py:attribute:: payment_form_fields

      A dictionary of form fields for payment details.

   .. py:method:: payment_is_valid_session(request)

      Check if the payment session is valid.

   .. py:method:: checkout_prepare(request, cart)

      Prepare the checkout process.

   .. py:method:: checkout_confirm_render(request)

      Render content for the checkout confirmation page.

      This is an abstract method, you **must** override this!

   .. py:method:: execute_payment(request, payment)

      Execute the payment.

   .. py:method:: calculate_fee(price)

      Calculate the fee for this payment method.

   .. py:method:: order_pending_mail_render(order)

      Render content for the pending order email.

   .. py:method:: payment_pending_render(request, payment)

      Render content for pending payment status.

   .. py:attribute:: abort_pending_allowed

      Whether aborting pending payments is allowed.

   .. py:method:: render_invoice_text(order, payment)

      Render text to be shown on the invoice.

   .. py:method:: order_change_allowed(order)

      Check if order changes are allowed for this payment provider.

   .. py:method:: payment_prepare(request, payment)

      Prepare a payment.

   .. py:method:: payment_control_render(request, payment)

      Render control interface for a payment.

   .. py:method:: payment_control_render_short(payment)

      Render short control interface for a payment.

   .. py:method:: payment_refund_supported(payment)

      Check if refunds are supported for this payment.

   .. py:method:: payment_partial_refund_supported(payment)

      Check if partial refunds are supported for this payment.

   .. py:method:: payment_presale_render(payment)

      Render payment information in the presale interface.

   .. py:method:: execute_refund(refund)

      Execute a refund.

   .. py:method:: refund_control_render(request, refund)

      Render control interface for a refund.

   .. py:method:: new_refund_control_form_render(request, payment)

      Render form for creating a new refund.

   .. py:method:: new_refund_control_form_process(request, payment, form_data)

      Process the new refund form.

   .. py:method:: api_payment_details(payment)

      Return payment details for API responses.

   .. py:method:: matching_id(payment)

      Return an identifier for matching payments.

   .. py:method:: shred_payment_info(payment)

      Shred sensitive payment information.

   .. py:method:: cancel_payment(payment)

      Cancel a payment.

   .. py:attribute:: is_implicit

      Whether this is an implicit payment provider.

   .. py:attribute:: is_meta

      Whether this is a meta payment provider.

   .. py:attribute:: test_mode_message

      Message to display when in test mode.

   .. py:attribute:: requires_invoice_immediately

      Whether this provider requires an invoice to be generated immediately.


Additional views
----------------

See also: :ref:`customview`.

For most simple payment providers it is more than sufficient to implement
some of the :py:class:`BasePaymentProvider` methods. However, in some cases
it is necessary to introduce additional views. One example is the PayPal
provider. It redirects the user to a PayPal website in the
:py:meth:`BasePaymentProvider.checkout_prepare` step of the checkout process
and provides PayPal with a URL to redirect back to. This URL points to a
view which looks roughly like this:

.. code-block:: python

    @login_required
    def success(request):
        pid = request.GET.get('paymentId')
        payer = request.GET.get('PayerID')
        # We stored some information in the session in checkout_prepare(),
        # let's compare the new information to double-check that this is about
        # the same payment
        if pid == request.session['payment_paypal_id']:
            # Save the new information to the user's session
            request.session['payment_paypal_payer'] = payer
            try:
                # Redirect back to the confirm page. We chose to save the
                # event ID in the user's session. We could also put this
                # information into a URL parameter.
                event = Event.objects.current.get(identity=request.session['payment_paypal_event'])
                return redirect(reverse('presale:event.checkout.confirm', kwargs={
                    'event': event.slug,
                    'organizer': event.organizer.slug,
                }))
            except Event.DoesNotExist:
                pass  # TODO: Display error message
        else:
            pass  # TODO: Display error message

If you do not want to provide a view of your own, you could even let PayPal
redirect directly back to the confirm page and handle the query parameters
inside :py:meth:`BasePaymentProvider.checkout_is_valid_session`. However,
because some external providers (not PayPal) force you to have a *constant*
redirect URL, it might be necessary to define custom views.
