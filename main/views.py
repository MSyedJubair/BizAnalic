from django.shortcuts import render, redirect
from django.http import HttpResponse
import logging
import pandas as pd
import json
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
import pdfplumber
import re

logger = logging.getLogger(__name__)
column_map = {
    "Type": ["Type", "Transaction Type", "TxnType"],
    "Amount": ["Amount", "Value", "Money", "Credit/Debit"],
    "Date": ["Date", "Txn Date", "Transaction Date"],
    "Description": ["Description", "Details", "Narration"]
}

def standardize_columns(df, column_map):
    rename_dict = {}
    for standard_name, possible_names in column_map.items():
        for col in df.columns:
            if col in possible_names:
                rename_dict[col] = standard_name
    return df.rename(columns=rename_dict)

def extract_transactions(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    lines = text.splitlines()
    transactions = []

    for line in lines:
        # Match: Date + Time + Description + Type + Amount + Balance
        match = re.match(
            r"(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}\s+(.+?)\s+(Credit|Debit)\s+([-]?\d+\.\d+)\s+([-]?\d+\.\d+)",
            line
        )
        if match:
            date, desc, t_type, amount, balance = match.groups()
            transactions.append([date, desc, t_type, float(amount), float(balance)])

    df = pd.DataFrame(transactions, columns=["Date", "Description", "Type", "Amount", "Balance"])
    return df

# Create your views here.
def home(request):
    return render(request, "General/index.html")

def dashboard(request):
    if request.session.get('uploaded_data'):
        data = request.session['uploaded_data']
        df = pd.DataFrame(data)

        # Basic totals
        total_income = df[df['Type'] == 'Credit']['Amount'].sum()
        total_expense = df[df['Type'] == 'Debit']['Amount'].sum()
        balance = total_income - total_expense

        # Extra KPIs
        avg_income = df[df['Type'] == 'Credit']['Amount'].mean()
        avg_expense = df[df['Type'] == 'Debit']['Amount'].mean()
        total_transactions = len(df)
        largest_transaction = df['Amount'].max()

        # Most frequent category/merchant
        most_frequent_category = (
            df['Description'].mode()[0] if not df['Description'].mode().empty else 'N/A'
        )

        # ---- Charts Data ---- #
        # Expense categories pie chart
        expense_by_category = (
            df[df['Type'] == 'Debit']
            .groupby('Description')['Amount']
            .sum()
            .sort_values(ascending=False)
            .head(6)  # top 6 categories
        )
        pie_labels = expense_by_category.index.tolist()
        pie_values = expense_by_category.values.tolist()

        # Monthly income vs expenses (bar chart)
        df['Date'] = pd.to_datetime(df['Date'])
        df['Month'] = df['Date'].dt.strftime('%b')
        monthly_data = df.groupby(['Month', 'Type'])['Amount'].sum().unstack(fill_value=0)
        bar_labels = monthly_data.index.tolist()
        bar_income = monthly_data.get('Credit', pd.Series([0]*len(bar_labels))).tolist()
        bar_expense = monthly_data.get('Debit', pd.Series([0]*len(bar_labels))).tolist()

        # Savings trend (line chart)
        monthly_balance = monthly_data.get('Credit', 0) - monthly_data.get('Debit', 0)
        line_labels = monthly_data.index.tolist()
        line_savings = monthly_balance.tolist()

        # Payment methods (donut chart) – if column exists
        if 'Method' in df.columns:
            method_data = df.groupby('Method')['Amount'].sum()
            donut_labels = method_data.index.tolist()
            donut_values = method_data.values.tolist()
        else:
            donut_labels, donut_values = [], []

        # Spending habits radar chart (group categories)
        radar_categories = ['Food','Transport','Shopping','Entertainment','Bills','Healthcare']
        radar_data = []
        for cat in radar_categories:
            radar_data.append(df[df['Description'].str.contains(cat, case=False, na=False)]['Amount'].sum())

        context = {
            # Summary Cards
            'total_income': round(total_income,2),
            'total_expense': round(total_expense,2),
            'balance': round(balance,2),
            'avg_income': round(avg_income,2) if not pd.isna(avg_income) else 0,
            'avg_expense': round(avg_expense,2) if not pd.isna(avg_expense) else 0,
            'total_transactions': total_transactions,
            'largest_transaction': round(largest_transaction,2),
            'most_frequent_category': most_frequent_category,

            # Chart Data (as JSON for Chart.js)
            'pie_labels': json.dumps(pie_labels),
            'pie_values': json.dumps(pie_values),
            'bar_labels': json.dumps(bar_labels),
            'bar_income': json.dumps(bar_income),
            'bar_expense': json.dumps(bar_expense),
            'line_labels': json.dumps(line_labels),
            'line_savings': json.dumps(line_savings),
            'donut_labels': json.dumps(donut_labels),
            'donut_values': json.dumps(donut_values),
            'radar_labels': json.dumps(radar_categories),
            'radar_values': json.dumps(radar_data),

            # Optional raw table
            'data': df.to_html(classes='table table-striped', index=False),
        }

        return render(request, "General/dashboard.html", context)

    return render(request, "General/dashboard.html")

def uploadfile(request):

    if request.method == 'POST':

        uploaded_file = request.FILES.get('statement')
        if uploaded_file:
            logger.info(f"Uploaded file: {uploaded_file.name}")
            
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
                df = standardize_columns(df, column_map)

            elif uploaded_file.name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(uploaded_file)
                df = standardize_columns(df, column_map)

            elif uploaded_file.name.endswith('.pdf'):
                df = extract_transactions(uploaded_file)
                df = standardize_columns(df, column_map)

            df['Date'] = df['Date'].astype(str)

            request.session['uploaded_data'] = df.to_dict(orient='records')

            return redirect('dashboard')
        else:
            logger.info("No file uploaded.")
            # Return 400 Bad Request
            return HttpResponse(
                "No file uploaded.",
                status=400
            )
        
    return HttpResponse(
        "This is a form data page",
        status=200
    )

def about(request):
    return render(request, "General/about.html")

def features(request):
    return render(request, "General/features.html")

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Sorry credentials!')
            return redirect('login')
            
    else:  
        return render(request, "registration/login.html", {"title": "Login"})
    
def user_logout(request):
    logout(request)
    return redirect('home')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['name']
        email = request.POST['email']
        password = request.POST['password']
        user = User.objects.create_user(username, email, password)
        user.save()
        messages.success(request, 'Account created successfully!')
        return redirect('login')
    else:
        return render(request, 'registration/signup.html')
    
def pleaseLogin(request):
    return render(request, 'Errors/pleaseLogin.html')