import json

from eventyay.base.models import SeatingPlan
from eventyay.base.models.seating import SeatingPlanLayoutValidator


def test_layout_with_only_required_fields():
    # The layout schema requires neither a row position nor a zone name.
    layout = json.dumps(
        {
            'name': 'Small Hall',
            'categories': [{'name': 'Stalls'}],
            'zones': [
                {
                    'position': {'x': 5, 'y': 5},
                    'rows': [
                        {
                            'row_number': '1',
                            'seats': [
                                {
                                    'seat_guid': '1-1',
                                    'seat_number': '1',
                                    'position': {'x': 10, 'y': 20},
                                    'category': 'Stalls',
                                }
                            ],
                        }
                    ],
                }
            ],
            'size': {'width': 100, 'height': 50},
        }
    )
    SeatingPlanLayoutValidator()(layout)

    (seat,) = SeatingPlan(name='Small Hall', layout=layout).iter_all_seats()

    assert (seat.guid, seat.zone, seat.x, seat.y) == ('1-1', '', 15, 25)
