import datetime


def get_egn_birth_date(egn):
    """
    Extract birth date from Bulgarian unique citizenship number (EGN).

    More details https://en.wikipedia.org/wiki/Unique_citizenship_number
    Information in Bulgarian for this can be found here
    http://www.grao.bg/esgraon.html#section2
    """
    try:
        year, month, day = int(egn[0:2]), int(egn[2:4]), int(egn[4:6])
    except (ValueError, TypeError):
        raise ValueError('First six characters must be numbers')

    if month >= 40:
        month -= 40
        year += 2000
    elif month >= 20:
        month -= 20
        year += 1800
    else:
        year += 1900

    return datetime.date(year, month, day)
