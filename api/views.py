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
        response['Content-Disposition'] = 'attachment; filename="transaction_history.pdf"'

        c = canvas.Canvas(buffer, pagesize=letter)

        # Title and header for the document
        c.setFont("Helvetica", 16)
        c.drawString(30, 750, f"Transaction History for {user.username}")

        # Define the table data
        data = [
            ["Date", "Description", "Amount", "Type"]  # Table headers
        ]
        for transaction in transactions:
            data.append([str(transaction.date), transaction.description, str(transaction.amount), transaction.transaction_type])

        # Create a table with data
        table = Table(data, colWidths=[100, 200, 100, 100])

        # Apply styling to the table
        style = TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),  # Table header color
            ('BACKGROUND', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ])
        table.setStyle(style)

        # Define starting y-position
        y_position = 650
        page_height = letter[1]  # 11 inches, or 792 points

        # Draw the table on the canvas
        table.wrapOn(c, 30, y_position)

        # Check if it fits on the page, otherwise create a new page
        if y_position - 100 - table.height < 0:  # Check if table exceeds page height
            c.showPage()
            y_position = page_height - 50  # Start a new page

        table.drawOn(c, 30, y_position - table.height)

        # If the content doesn't fit on the first page, create another page for additional rows
        remaining_transactions = transactions[10:]  # You can adjust this to determine how many fit per page
        data = [["Date", "Description", "Amount", "Type"]]  # Headers for second page
        for transaction in remaining_transactions:
            data.append([str(transaction.date), transaction.description, str(transaction.amount), transaction.transaction_type])

        # Create new table for remaining transactions
        table = Table(data, colWidths=[100, 200, 100, 100])
        table.setStyle(style)
        table.wrapOn(c, 30, y_position - 100)  # Adjust y-position to fit next page
        table.drawOn(c, 30, y_position - table.height)

        c.showPage()
        c.save()

        buffer.seek(0)
        response.write(buffer.getvalue())
        return response
