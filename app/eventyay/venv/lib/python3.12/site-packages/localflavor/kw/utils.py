from datetime import date


def is_valid_civil_id(cid):
    """
    Checks the validity of a Kuwaiti Civil ID number
    by verifying the following:
      * The number should consist of 12 digits
      * The first digit should be 1, 2, or 3
      * The extracted birthdate should be a valid date
      * The checksum should be equal to the last digit of the Civil ID
    """
    # Civil ID can only start with 1, 2, or 3 till year 2100
    if len(cid) != 12 or not cid.isdigit() or cid[0] not in ('1', '2', '3'):
        return False

    # calculate the Civil ID checksum
    weight = (2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    initial = sum(x * y for x, y in zip(weight, map(int, cid[:-1]))) % 11
    checksum = 11 - initial

    # extract birthdate to check if it's a valid date
    try:
        get_birthdate_from_civil_id(cid)
    except ValueError:
        return False

    # verify if the checksum matches the last digit
    return checksum == int(cid[11])


def get_birthdate_from_civil_id(cid):
    """
    Extracts the birthdate from a Kuwaiti Civil ID number
    """
    by_century = {
        '1': '18',
        '2': '19',
        '3': '20'
    }
    if cid[0] not in ('1', '2', '3'):
        raise ValueError('Invalid first digit')
    year = int('{}{}'.format(by_century[cid[0]], cid[1:3]))
    month = int(cid[3:5])
    day = int(cid[5:7])
    return date(year, month, day)
