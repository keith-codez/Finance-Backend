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
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.units import inch
from io import BytesIO
from django.db import models


@api_view(['GET'])
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
        response['Content-Disposition'] = f'attachment; filename="transaction_history_{user.username}.pdf"'

        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # **Header Section**
        c.setFont("Helvetica-Bold", 16)
        c.drawString(200, height - 50, "Bank Statement")
        
        c.setFont("Helvetica", 12)
        c.drawString(30, height - 70, f"Account Holder: {user.username}")
        c.drawString(30, height - 85, "Statement Period: Last Transactions")
        
        # **Table Data**
        data = [["Date", "Description", "Amount", "Type"]]  # Table headers
        for transaction in transactions:
            data.append([
                transaction.date.strftime('%d-%m-%Y'),
                transaction.description,
                f"${transaction.amount:.2f}",
                transaction.transaction_type
            ])

        # **Create Table**
        table = Table(data, colWidths=[1.5 * inch, 2.5 * inch, 1.5 * inch, 1.5 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),  # Header row background
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),  # Header text color
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Center align text
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Bold headers
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),  # Space for headers
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),  # Alternate row color
            ('GRID', (0, 0), (-1, -1), 1, colors.black),  # Add gridlines
        ]))

        # **Table Positioning**
        table.wrapOn(c, width, height)
        table.drawOn(c, 30, height - 150)  # Position table on the PDF

        # **Footer**
        c.setFont("Helvetica", 10)
        c.drawString(30, 30, "Thank you for banking with us!")
        c.drawString(450, 30, f"Generated on: {request.user.username}")

        c.showPage()
        c.save()

        buffer.seek(0)
        response.write(buffer.getvalue())
        return response
