import csv

from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Q
from django.utils import timezone
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib import messages

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)

from .models import Expense


@login_required
def dashboard(request):
    expenses = Expense.objects.filter(
        user=request.user
    ).order_by('-date')

    search = request.GET.get('search', '').strip()
    category = request.GET.get('category', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    if search:
        expenses = expenses.filter(
            Q(category__icontains=search) |
            Q(description__icontains=search)
        )

    if category:
        expenses = expenses.filter(category=category)

    if start_date:
        expenses = expenses.filter(date__gte=start_date)

    if end_date:
        expenses = expenses.filter(date__lte=end_date)

    total_expense = expenses.aggregate(
        total=Sum('amount')
    )['total'] or 0

    expense_count = expenses.count()

    category_summary = (
        expenses
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    chart_labels = [
        item['category']
        for item in category_summary
    ]

    chart_data = [
        float(item['total'])
        for item in category_summary
    ]

    current_month = timezone.now().month
    current_year = timezone.now().year

    monthly_expense = expenses.filter(
        date__month=current_month,
        date__year=current_year
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0

    categories = (
        Expense.objects
        .filter(user=request.user)
        .values_list('category', flat=True)
        .distinct()
        .order_by('category')
    )

    paginator = Paginator(expenses, 5)
    page_number = request.GET.get('page')
    expenses_page = paginator.get_page(page_number)

    context = {
        'expenses': expenses_page,
        'paginator': paginator,
        'total_expense': total_expense,
        'expense_count': expense_count,
        'category_summary': category_summary,
        'monthly_expense': monthly_expense,
        'search': search,
        'category': category,
        'categories': categories,
        'start_date': start_date,
        'end_date': end_date,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    }

    return render(request, 'expenses/dashboard.html', context)


@login_required
def add_expense(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        category = request.POST.get('category', '').strip()
        description = request.POST.get('description', '').strip()
        date = request.POST.get('date')

        if amount and category and date:
            Expense.objects.create(
                user=request.user,
                amount=amount,
                category=category,
                description=description,
                date=date
            )

            messages.success(
                request,
                'Expense added successfully!'
            )

            return redirect('dashboard')

    return render(request, 'expenses/add_expense.html')


@login_required
def edit_expense(request, id):
    expense = get_object_or_404(
        Expense,
        id=id,
        user=request.user
    )

    if request.method == 'POST':
        expense.amount = request.POST.get('amount')
        expense.category = request.POST.get('category', '').strip()
        expense.description = request.POST.get('description', '').strip()
        expense.date = request.POST.get('date')
        expense.save()

        messages.success(
            request,
            'Expense updated successfully!'
        )

        return redirect('dashboard')

    return render(request, 'expenses/edit_expense.html', {
        'expense': expense
    })


@login_required
def delete_expense(request, id):
    expense = get_object_or_404(
        Expense,
        id=id,
        user=request.user
    )

    expense.delete()

    messages.success(
        request,
        'Expense deleted successfully!'
    )

    return redirect('dashboard')


def signup(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if not username or not password or not confirm_password:
            return render(request, 'expenses/signup.html', {
                'error': 'All fields are required.'
            })

        if password != confirm_password:
            return render(request, 'expenses/signup.html', {
                'error': 'Passwords do not match.'
            })

        if User.objects.filter(username=username).exists():
            return render(request, 'expenses/signup.html', {
                'error': 'Username already exists.'
            })

        try:
            validate_password(password)
        except ValidationError as e:
            return render(request, 'expenses/signup.html', {
                'error': ' '.join(e.messages)
            })

        user = User.objects.create_user(
            username=username,
            password=password
        )

        login(request, user)

        messages.success(
            request,
            'Account created successfully!'
        )

        return redirect('dashboard')

    return render(request, 'expenses/signup.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)

            messages.success(
                request,
                'Login successful!'
            )

            return redirect('dashboard')

        return render(request, 'expenses/login.html', {
            'error': 'Invalid username or password.'
        })

    return render(request, 'expenses/login.html')


def logout_view(request):
    logout(request)

    messages.success(
        request,
        'You have been logged out.'
    )

    return redirect('login')


@login_required
def export_csv(request):
    expenses = Expense.objects.filter(
        user=request.user
    ).order_by('-date')

    search = request.GET.get('search', '').strip()
    category = request.GET.get('category', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    if search:
        expenses = expenses.filter(
            Q(category__icontains=search) |
            Q(description__icontains=search)
        )

    if category:
        expenses = expenses.filter(category=category)

    if start_date:
        expenses = expenses.filter(date__gte=start_date)

    if end_date:
        expenses = expenses.filter(date__lte=end_date)

    response = HttpResponse(
        content_type='text/csv'
    )

    response['Content-Disposition'] = (
        'attachment; filename="expenses.csv"'
    )

    writer = csv.writer(response)

    writer.writerow([
        'Date',
        'Category',
        'Description',
        'Amount'
    ])

    for expense in expenses:
        writer.writerow([
            expense.date,
            expense.category,
            expense.description or '',
            expense.amount
        ])

    return response


@login_required
def export_pdf(request):
    expenses = Expense.objects.filter(
        user=request.user
    ).order_by('-date')

    search = request.GET.get('search', '').strip()
    category = request.GET.get('category', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    if search:
        expenses = expenses.filter(
            Q(category__icontains=search) |
            Q(description__icontains=search)
        )

    if category:
        expenses = expenses.filter(category=category)

    if start_date:
        expenses = expenses.filter(date__gte=start_date)

    if end_date:
        expenses = expenses.filter(date__lte=end_date)

    response = HttpResponse(
        content_type='application/pdf'
    )

    response['Content-Disposition'] = (
        'attachment; filename="expense_report.pdf"'
    )

    document = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()

    title = Paragraph(
        'Expense Tracker Report',
        styles['Title']
    )

    user_info = Paragraph(
        f'User: {request.user.username}',
        styles['Normal']
    )

    report_date = Paragraph(
        f'Report Date: {timezone.now().strftime("%d-%m-%Y")}',
        styles['Normal']
    )

    total_expense = expenses.aggregate(
        total=Sum('amount')
    )['total'] or 0

    total_info = Paragraph(
        f'Total Expenses: Rs. {total_expense}',
        styles['Normal']
    )

    data = [
        ['Date', 'Category', 'Description', 'Amount']
    ]

    for expense in expenses:
        data.append([
            str(expense.date),
            expense.category,
            expense.description or '',
            f'Rs. {expense.amount}'
        ])

    if len(data) == 1:
        data.append([
            '',
            'No expenses',
            'No matching records found',
            'Rs. 0'
        ])

    table = Table(
        data,
        colWidths=[75, 90, 220, 70]
    )

    table.setStyle(
        TableStyle([
            (
                'BACKGROUND',
                (0, 0),
                (-1, 0),
                colors.HexColor('#0d6efd')
            ),
            (
                'TEXTCOLOR',
                (0, 0),
                (-1, 0),
                colors.white
            ),
            (
                'FONTNAME',
                (0, 0),
                (-1, 0),
                'Helvetica-Bold'
            ),
            (
                'GRID',
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),
            (
                'ALIGN',
                (3, 1),
                (3, -1),
                'RIGHT'
            ),
            (
                'VALIGN',
                (0, 0),
                (-1, -1),
                'MIDDLE'
            ),
            (
                'PADDING',
                (0, 0),
                (-1, -1),
                6
            ),
        ])
    )

    document.build([
        title,
        user_info,
        report_date,
        total_info,
        Spacer(1, 15),
        table
    ])

    return response