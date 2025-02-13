from rest_framework import serializers
from .models import Wallet, Transaction

class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['user', 'balance']

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['date', 'description', 'amount', 'transaction_type']
        read_only_fields = ['date', 'description', 'amount','transaction_type']