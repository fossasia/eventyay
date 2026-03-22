from enum import Enum


class ItemType(Enum):
    """Item type.

    If no item type matches the type of item being sold, it is currently not
    supported by pyvat.
    """

    generic_physical_good = 1
    """Generic physical good.
    """

    generic_electronic_service = 2
    """Generic electronic service.

    Any electronic service that is not covered by a more specific item type.
    """

    generic_telecommunications_service = 3
    """Generic telecommunications service.

    Any telecommunications service that is not covered by a more specific item
    type.
    """

    generic_broadcasting_service = 4
    """Generic broadcasting service.

    Any broadcasting service that is not covered by a more specific item type.
    """

    prepaid_broadcasting_service = 5
    """Pre-paid service provided by broadcasting company.
    """

    ebook = 6
    """E-book.
    """

    enewspaper = 7
    """E-newspaper.
    """

    @property
    def is_electronic_service(self):
        return self in frozenset([ItemType.generic_electronic_service,
                                  ItemType.ebook,
                                  ItemType.enewspaper])

    @property
    def is_telecommunications_service(self):
        return self in frozenset([ItemType.generic_telecommunications_service])

    @property
    def is_broadcasting_service(self):
        return self in frozenset([ItemType.generic_broadcasting_service,
                                  ItemType.prepaid_broadcasting_service])
