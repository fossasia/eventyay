from django.db import models


class ReferencedBitPayObject(models.Model):
    reference = models.CharField(max_length=190, db_index=True, unique=True)
    order = models.ForeignKey("base.Order", on_delete=models.CASCADE)
    payment = models.ForeignKey(
        "base.OrderPayment", null=True, blank=True, on_delete=models.CASCADE
    )
