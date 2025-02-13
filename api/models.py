from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now
from django.db.models import Sum
# Create your models here.

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = short_description = 'Balance'
    def calculate_balance(self):
        # Sum up all debit transactions
        debit_sum = self.transactions.filter(transaction_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0
        # Sum up all credit transactions
        credit_sum = self.transactions.filter(transaction_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0

        # Return the net balance (credits - debits)
        return debit_sum - credit_sum
    def balance(self):
        return self.calculate_balance()


    def __str__(self):
        return f"{self.user.username}" 


class Transaction(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    date = models.DateField(default=now)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=[('credit', 'Credit'), ('debit', 'Debit')])


    def __str__(self):
        return f"{self.wallet.user.username} - {self.description} - {self.amount}"
    
    class Meta:
        ordering = ['-date']