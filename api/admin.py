from django.contrib import admin
from .models import Wallet, Transaction
import pandas as pd
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.timezone import now
from django.urls import path
from django import forms
from django.http import HttpResponseRedirect
from datetime import datetime

# CSV Upload Form
class CSVUploadForm(forms.Form):
    csv_file = forms.FileField()

# Inline Transaction Management inside WalletAdmin
class TransactionInline(admin.TabularInline):  # Tabular format for transactions
    model = Transaction
    extra = 1  # Allows adding new transactions inline
    readonly_fields = ('formatted_date',)  # Readable date format
    fields = ('formatted_date', 'description', 'amount', 'transaction_type')

    def formatted_date(self, obj):
        return obj.date.strftime('%d-%m-%Y')
    formatted_date.short_description = 'Date'

# Wallet Admin: Displays transactions inline + CSV Upload
@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance')  # Show the balance
    readonly_fields = ("balance",)  # Make balance read-only
    search_fields = ('user__username', 'balance')
    inlines = [TransactionInline]  # Show transactions inside Wallet
    actions = ['upload_csv_action']  # CSV Upload action
    
    def upload_csv_action(self, request, queryset):
        if len(queryset) != 1:
            self.message_user(request, "Select only one Wallet to upload transactions.", level='error')
            return redirect("..")
        wallet = queryset.first()
        return redirect(f"upload-csv/{wallet.id}/")  # Redirect to upload page

    upload_csv_action.short_description = "Upload CSV Transactions"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-csv/<int:wallet_id>/', self.admin_site.admin_view(self.upload_csv_view), name="upload_csv"),
        ]
        return custom_urls + urls

    def upload_csv_view(self, request, wallet_id):
        wallet = Wallet.objects.get(id=wallet_id)

        if 'csv_file' in request.FILES:
            csv_file = request.FILES['csv_file']

            if not csv_file.name.endswith('csv'):
                messages.error(request, 'Invalid file format. Please upload a CSV file.')
                return redirect("..")

            try:
                df = pd.read_csv(csv_file)
            except Exception as e:
                messages.error(request, f"Error reading CSV: {e}")
                return redirect("..")

            required_columns = {"description", "amount", "transaction_type", "date"}
            if not required_columns.issubset(df.columns):
                messages.error(request, "CSV file must include: description, amount, transaction_type, date")
                return redirect("..")

            # Create transactions linked to the selected wallet
            for _, row in df.iterrows():
                try:
                    # Normalize and convert the date format to YYYY-MM-DD
                    date_str = str(row["date"]).strip()
                    date_str = date_str.replace("/", "-")  # Replace / with - if needed

                    try:
                        date_obj = datetime.strptime(date_str, "%d-%m-%Y").date()
                    except ValueError:
                        date_obj = datetime.strptime(date_str, "%d/%m/%Y").date()

                    # Create the transaction linked to the selected wallet (no need for `user` here)
                    Transaction.objects.create(
                        wallet=wallet,
                        description=row["description"],
                        amount=row["amount"],
                        transaction_type=row["transaction_type"],
                        date=date_obj  # Save in the correct format
                    )

                except Exception as e:
                    messages.warning(request, f"Skipping row due to error: {e}")

            messages.success(request, f"Transactions imported successfully for {wallet.user.username}")
            return redirect(f"/admin/api/wallet/{wallet.id}/change/")  # Redirect back to wallet page

        else:
            form = CSVUploadForm()

        return render(request, 'admin/csv_upload_form.html', {'form': form, 'title': f'Upload CSV for {wallet.user.username}'})

# Register Transaction separately in case needed
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'formatted_date', 'description', 'amount', 'transaction_type')
    list_filter = ('transaction_type', 'date')
    search_fields = ('wallet__user__username', 'description')

    def formatted_date(self, obj):
        return obj.date.strftime('%d-%m-%Y')

    formatted_date.short_description = 'Date'
