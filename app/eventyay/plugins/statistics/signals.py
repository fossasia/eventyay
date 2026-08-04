from eventyay.base.signals import order_paid, order_placed


def clear_cache(sender, *args, **kwargs):
    suffixes = ['all']
    if getattr(sender, 'has_subevents', False):
        suffixes.extend([str(pk) for pk in sender.subevents.values_list('pk', flat=True)])

    prefixes = (
        'statistics_obd_data',
        'statistics_obp_data',
        'statistics_rev_data',
    )
    sender.cache.delete_many(
        [f'{prefix}{suffix}' for prefix in prefixes for suffix in suffixes]
    )


order_placed.connect(clear_cache)
order_paid.connect(clear_cache)
