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

        # Get the user's wallet balance
        wallet, _ = Wallet.objects.get_or_create(user=user)
        total_credits = Transaction.objects.filter(wallet=wallet, transaction_type='credit').aggregate(total=models.Sum('amount'))['total'] or 0
        total_debits = Transaction.objects.filter(wallet=wallet, transaction_type='debit').aggregate(total=models.Sum('amount'))['total'] or 0
        balance = total_debits - total_credits  # Calculate balance

        # Create a buffer to hold the PDF data
        buffer = BytesIO()

        # Create the PDF document
        doc = SimpleDocTemplate(buffer, pagesize=letter)

        # Get default styles
        styles = getSampleStyleSheet()

        # Add title and balance display
        title = Paragraph(f"<b>Transaction History for {user.username}</b>", styles["Title"])
        balance_text = Paragraph(f"<b>Current Balance: ${balance:.2f}</b>", styles["Normal"])

        # Define the table headers
        data = [["Date", "Description", "Amount ($)", "Type"]]

        # Add transaction data
        for transaction in transactions:
            data.append([str(transaction.date), transaction.description, f"${transaction.amount:.2f}", transaction.transaction_type])

        # Create a table with proper column widths
        table = Table(data, colWidths=[100, 200, 100, 100])

        # Apply table styling
        style = TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),  # Header color
            ('BACKGROUND', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ])
        table.setStyle(style)

        # Build the PDF with title, balance, and table
        elements = [
            title,
            Spacer(1, 12),  # Space after title
            balance_text,
            Spacer(1, 20),  # Space before table
            table
        ]

        doc.build(elements)

        # Prepare the HttpResponse
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="transaction_history.pdf"'

        # Move to the start of the buffer and write the PDF content to the response
        buffer.seek(0)
        response.write(buffer.getvalue())

        return response