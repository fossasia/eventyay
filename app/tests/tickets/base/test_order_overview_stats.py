from eventyay.base.services.stats import DummyObject, group_overview_by_classification


def _product(name, admission, num):
    product = DummyObject()
    product.name = name
    product.admission = admission
    product.num = num
    product.has_variations = False
    product.provider = ''
    return product


def _category(name, num, category_id=None):
    category = DummyObject()
    category.name = name
    category.num = num
    if category_id is not None:
        category.id = category_id
    return category


def test_group_overview_by_classification_falls_back_to_product_type():
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
    # No persisted categories (id=None) → fall back to Admission / Non-Admission.
    products_by_category = [
        (
            _category(
                'Uncategorized',
                {
                    'canceled': (1, 0, 0),
                    'expired': (0, 0, 0),
                    'unapproved': (0, 0, 0),
                    'pending': (3, 30, 27),
                    'paid': (5, 45, 40),
                    'total': (8, 75, 67),
                },
            ),
            [ticket, merch, uncategorized_product],
        ),
    ]

    groups = group_overview_by_classification(products_by_category)

    assert [str(group.name) for group, _items in groups] == ['Tickets', 'Products', 'Uncategorized']
    assert groups[0][1] == [ticket]
    assert groups[1][1] == [merch]
    assert groups[2][1] == [uncategorized_product]
    assert groups[0][0].num['total'] == ticket.num['total']


def test_group_overview_by_classification_keeps_custom_categories():
    vip = _product(
        'VIP Pass',
        True,
        {
            'canceled': (0, 0, 0),
            'expired': (0, 0, 0),
            'unapproved': (0, 0, 0),
            'pending': (0, 0, 0),
            'paid': (2, 200, 180),
            'total': (2, 200, 180),
        },
    )
    workshop = _product(
        'Workshop',
        False,
        {
            'canceled': (0, 0, 0),
            'expired': (0, 0, 0),
            'unapproved': (0, 0, 0),
            'pending': (1, 50, 45),
            'paid': (1, 50, 45),
            'total': (2, 100, 90),
        },
    )
    products_by_category = [
        (
            _category(
                'VIP Passes',
                vip.num,
                category_id=10,
            ),
            [vip],
        ),
        (
            _category(
                'Workshops',
                workshop.num,
                category_id=11,
            ),
            [workshop],
        ),
    ]

    groups = group_overview_by_classification(products_by_category)

    assert [str(group.name) for group, _items in groups] == ['VIP Passes', 'Workshops']
    assert groups[0][1] == [vip]
    assert groups[1][1] == [workshop]


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
            (_category('Uncategorized', ticket.num), [ticket]),
            (fees_category, [fee_product]),
        ]
    )

    assert [str(group.name) for group, _items in groups] == ['Tickets', 'Fees']
    assert groups[-1][1] == [fee_product]


def test_group_overview_by_classification_keeps_fees_last_with_custom_categories():
    merch = _product(
        'Shirt',
        False,
        {
            'canceled': (0, 0, 0),
            'expired': (0, 0, 0),
            'unapproved': (0, 0, 0),
            'pending': (0, 0, 0),
            'paid': (1, 15, 13),
            'total': (1, 15, 13),
        },
    )
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

    groups = group_overview_by_classification(
        [
            (_category('Merch', merch.num, category_id=5), [merch]),
            (_category('Fees', fee_product.num), [fee_product]),
        ]
    )

    assert [str(group.name) for group, _items in groups] == ['Merch', 'Fees']
    assert groups[-1][1] == [fee_product]
