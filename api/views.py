from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.shortcuts import render
from rest_framework.response import Response
from .models import Wallet, Transaction
from .serializers import WalletSerializer, TransactionSerializer
from rest_framework.views import APIView
from django.http import HttpResponse
from django.template.loader import get_template
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from django.db import models



@api_view (['GET'])
@permission_classes([IsAuthenticated])
def get_wallet(request):
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    serializer = WalletSerializer(wallet)

    total_credits = Transaction.objects.filter(wallet=wallet, transaction_type='credit').aggregate(total=models.Sum('amount'))['total'] or 0
    total_debits = Transaction.objects.filter(wallet=wallet, transaction_type='debit').aggregate(total=models.Sum('amount'))['total'] or 0
    
    balance = total_debits - total_credits


    wallet_data = serializer.data
    wallet_data['balance'] = balance


    return Response(wallet_data)

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({"error": "Username and password are required"}, status=400)
    
    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already taken"}, status=400)
    

    user = User.objects.create_user(username=username, password=password)
    Wallet.objects.create(user=user)
    return Response({"message": "User registered successfully"}, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    username = request.data.get('username')
    password = request.data.get('password')

    user = User.objects.filter(username=username).first()
    if user and user.check_password(password):
        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token)
        })
    
    return Response({"error": "Invalid credentials"}, status=400)


class TransactionHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        transactions = Transaction.objects.filter(wallet__user=user)
        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data)
    

class TransactionHistoryPDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        transactions = Transaction.objects.filter(wallet__user=user)

        buffer = BytesIO()
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="transaction_history.pdf"'

        c = canvas.Canvas(buffer, pagesize=letter)

        c.setFont("Helvetica", 12)
        c.drawString(30, 750, "Transaction History")
        c.drawString(30, 730, "Date | Description | Amount | Type")

        y_position = 710
        for transaction in transactions:
            c.drawString(30, y_position, f"{transaction.date} | {transaction.description} | {transaction.amount} | {transaction.transaction_type}")
            y_position -= 20

            if y_position < 50:
                c.showPage()
                c.setFont("Helvetica", 12)
                c.drawString(30, 750, "Transaction History for {user.username}")
                c.drawString(30, 730, "Date | Description | Amount | Type")
                y_position = 710

        c.showPage()
        c.save()

        buffer.seek(0)
        response.write(buffer.getvalue())
        return response
