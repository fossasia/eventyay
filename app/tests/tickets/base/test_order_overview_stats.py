from eventyay.base.services.stats import DummyObject, group_overview_by_classification


def _product(name, admission, num):
    product = DummyObject()
    product.name = name
    product.admission = admission
    product.num = num
    product.has_variations = False
    product.provider = ''
    return product


def _category(name, num):
    category = DummyObject()
    category.name = name
    category.num = num
    return category


def test_group_overview_by_classification_splits_tickets_and_products():
    ticket = _product(
        'Standard ticket',
        True,
        {
            'canceled': (1, 0, 0),
            'expired': (0, 0, 0),
            'unapproved': (0, 0, 0),
            'pending': (2, 20, 18),
            'paid': (3, 30, 27),
            'total': (5, 50, 45),
        },
    )
    merch = _product(
        'T-shirt',
        False,
        {
            'canceled': (0, 0, 0),
            'expired': (0, 0, 0),
            'unapproved': (0, 0, 0),
            'pending': (1, 10, 9),
            'paid': (1, 10, 9),
            'total': (2, 20, 18),
        },
    )
    uncategorized_product = _product(
        'Mystery item',
        None,
        {
            'canceled': (0, 0, 0),
            'expired': (0, 0, 0),
            'unapproved': (0, 0, 0),
            'pending': (0, 0, 0),
            'paid': (1, 5, 4),
            'total': (1, 5, 4),
        },
    )
    products_by_category = [
        (
            _category(
                'Tickets',
                {
                    'canceled': (1, 0, 0),
                    'expired': (0, 0, 0),
                    'unapproved': (0, 0, 0),
                    'pending': (2, 20, 18),
                    'paid': (3, 30, 27),
                    'total': (5, 50, 45),
                },
            ),
            [ticket],
        ),
        (
            _category(
                'Merchandise',
                {
                    'canceled': (0, 0, 0),
                    'expired': (0, 0, 0),
                    'unapproved': (0, 0, 0),
                    'pending': (1, 10, 9),
                    'paid': (1, 10, 9),
                    'total': (2, 20, 18),
                },
            ),
            [merch],
        ),
        (
            _category(
                'Other',
                {
                    'canceled': (0, 0, 0),
                    'expired': (0, 0, 0),
                    'unapproved': (0, 0, 0),
                    'pending': (0, 0, 0),
                    'paid': (1, 5, 4),
                    'total': (1, 5, 4),
                },
            ),
            [uncategorized_product],
        ),
    ]

    groups = group_overview_by_classification(products_by_category)

    assert [str(group.name) for group, _items in groups] == ['Tickets', 'Products', 'Uncategorized']
    assert groups[0][1] == [ticket]
    assert groups[1][1] == [merch]
    assert groups[2][1] == [uncategorized_product]
    assert groups[0][0].num['total'] == ticket.num['total']


def test_group_overview_by_classification_keeps_fees_group_last():
    fee_product = _product(
        'Payment fee',
        None,
        {
            'canceled': (0, 0, 0),
            'expired': (0, 0, 0),
            'unapproved': (0, 0, 0),
            'pending': (0, 0, 0),
            'paid': (1, 2, 2),
            'total': (1, 2, 2),
        },
    )
    fees_category = _category(
        'Fees',
        {
            'canceled': (0, 0, 0),
            'expired': (0, 0, 0),
            'unapproved': (0, 0, 0),
            'pending': (0, 0, 0),
            'paid': (1, 2, 2),
            'total': (1, 2, 2),
        },
    )
    ticket = _product(
        'Ticket',
        True,
        {
            'canceled': (0, 0, 0),
            'expired': (0, 0, 0),
            'unapproved': (0, 0, 0),
            'pending': (0, 0, 0),
            'paid': (1, 10, 9),
            'total': (1, 10, 9),
        },
    )

    groups = group_overview_by_classification(
        [
            (_category('Tickets', ticket.num), [ticket]),
            (fees_category, [fee_product]),
        ]
    )

    assert [str(group.name) for group, _items in groups] == ['Tickets', 'Fees']
    assert groups[-1][1] == [fee_product]
