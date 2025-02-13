from django.urls import path 
from .views import get_wallet, register_user, login_user, TransactionHistoryView, TransactionHistoryPDFView

urlpatterns = [
    path('register/', register_user, name='register_user'), 
    path('login/', login_user, name='login_user'), 
    path('wallet/', get_wallet, name='get_wallet'),
    path('transactions/', TransactionHistoryView.as_view(), name='transaction_history'),
    path('transactions/pdf/', TransactionHistoryPDFView.as_view(), name='transaction-history-pdf'),
]