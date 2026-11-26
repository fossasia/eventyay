from django.utils.translation import gettext_lazy as _

from eventyay.base.anonymizer import REDACTED, BaseTicketingAnonymizer
from eventyay.base.models import Order

from .models import BankTransaction


class BankTransactionAnonymizer(BaseTicketingAnonymizer):
    identifier = 'bank_transactions'
    verbose_name = _('Imported bank transactions')

    def anonymize_order(self, order: Order) -> None:
        # Amount, date, state and checksum stay, so the import history still reconciles and re-imports
        # are still recognised as duplicates.
        BankTransaction.objects.filter(order=order).update(payer=REDACTED, iban='', bic='', reference=REDACTED)
