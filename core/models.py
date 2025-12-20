from django.db import models
from django.contrib.auth.models import User
import uuid


class Group(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_groups'
    )
    members = models.ManyToManyField(
        User, related_name='member_groups'
    )
    group_code = models.CharField(max_length=10, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.group_code:
            self.group_code = str(uuid.uuid4())[:8]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Expense(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='expenses')
    paid_by = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)

    # ✅ OPTIONAL RECEIPT
    receipt = models.ImageField(
        upload_to='receipts/',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.description} - {self.amount}"


class Settlement(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    paid_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='settlements_made'
    )
    paid_to = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='settlements_received'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.paid_by} paid {self.paid_to} ₹{self.amount}"
