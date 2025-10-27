Additional database indices
===========================

If you have a large Eventyay database, some features such as search for orders or events might turn pretty slow.
For PostgreSQL, we have compiled a list of additional database indexes that you can add to speed things up.
Just like any index, they in turn make write operations insignificantly slower and cause the database to use
more disk space.

The indexes aren't automatically created by Eventyay since Django does not allow us to do so only on PostgreSQL
(and they won't work on other databases). Also, they're really not necessary if you're not having tens of
thousands of records in your database.

However, this also means they won't automatically adapt if some of the referred fields change in future updates of Eventyay
and you might need to re-check this page and change them manually.

Here is the currently recommended set of commands::

    CREATE EXTENSION pg_trgm;

    CREATE INDEX CONCURRENTLY eventyay_addidx_event_slug
        ON eventyaybase_event
        USING gin (upper("slug") gin_trgm_ops);
    CREATE INDEX CONCURRENTLY eventyay_addidx_event_name
        ON eventyaybase_event
        USING gin (upper("name") gin_trgm_ops);
    CREATE INDEX CONCURRENTLY eventyay_addidx_order_code
        ON eventyaybase_order
        USING gin (upper("code") gin_trgm_ops);
    CREATE INDEX CONCURRENTLY eventyay_addidx_voucher_code
        ON eventyaybase_voucher
        USING gin (upper("code") gin_trgm_ops);
    CREATE INDEX CONCURRENTLY eventyay_addidx_invoice_nu1
        ON "eventyaybase_invoice" (UPPER("invoice_no"));
    CREATE INDEX CONCURRENTLY eventyay_addidx_invoice_nu2
        ON "eventyaybase_invoice" (UPPER("full_invoice_no"));
    CREATE INDEX CONCURRENTLY eventyay_addidx_organizer_name
        ON eventyaybase_organizer
        USING gin (upper("name") gin_trgm_ops);
    CREATE INDEX CONCURRENTLY eventyay_addidx_organizer_slug
        ON eventyaybase_organizer
        USING gin (upper("slug") gin_trgm_ops);
    CREATE INDEX CONCURRENTLY eventyay_addidx_order_email
        ON eventyaybase_order
        USING gin (upper("email") gin_trgm_ops);
    CREATE INDEX CONCURRENTLY eventyay_addidx_order_comment
        ON eventyaybase_order
        USING gin (upper("comment") gin_trgm_ops);
    CREATE INDEX CONCURRENTLY eventyay_addidx_orderpos_name
        ON eventyaybase_orderposition
        USING gin (upper("attendee_name_cached") gin_trgm_ops);
    CREATE INDEX CONCURRENTLY eventyay_addidx_orderpos_scret
        ON eventyaybase_orderposition
        USING gin (upper("secret") gin_trgm_ops);
    CREATE INDEX CONCURRENTLY eventyay_addidx_orderpos_email
        ON eventyaybase_orderposition
        USING gin (upper("attendee_email") gin_trgm_ops);
    CREATE INDEX CONCURRENTLY eventyay_addidx_ia_name
        ON eventyaybase_invoiceaddress
        USING gin (upper("name_cached") gin_trgm_ops);
    CREATE INDEX CONCURRENTLY eventyay_addidx_ia_company
        ON eventyaybase_invoiceaddress
        USING gin (upper("company") gin_trgm_ops);
    CREATE INDEX CONCURRENTLY eventyay_addidx_orderpos_email_upper
        ON public.eventyaybase_orderposition (upper((attendee_email)::text));
    CREATE INDEX CONCURRENTLY eventyay_addidx_voucher_code_upper
        ON public.eventyaybase_voucher (upper((code)::text));


Also, if you use our ``Eventyay-shipping`` plugin::

    CREATE INDEX CONCURRENTLY eventyay_addidx_sa_name
        ON eventyay_shipping_shippingaddress
        USING gin (upper("name") gin_trgm_ops);
    CREATE INDEX CONCURRENTLY eventyay_addidx_sa_company
        ON eventyay_shipping_shippingaddress
        USING gin (upper("company") gin_trgm_ops);

