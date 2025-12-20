from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from decimal import Decimal
from .models import Group, Expense, Settlement


# =========================
# AUTH
# =========================

def signup_view(request):
    if request.method == "POST":
        User.objects.create_user(
            username=request.POST['username'],
            email=request.POST['email'],
            password=request.POST['password']
        )
        return redirect('/login/')
    return render(request, 'auth/signup.html')


def login_view(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST['username'],
            password=request.POST['password']
        )
        if user:
            login(request, user)
            return redirect('/dashboard/')
    return render(request, 'auth/login.html')


def logout_view(request):
    logout(request)
    return redirect('/login/')


# =========================
# DASHBOARD
# =========================

def dashboard(request):
    groups = request.user.member_groups.all()
    return render(request, 'auth/dashboard.html', {'groups': groups})


# =========================
# GROUPS
# =========================

def create_group(request):
    if request.method == "POST":
        group = Group.objects.create(
            name=request.POST['name'],
            created_by=request.user
        )
        group.members.add(request.user)
        return redirect('/dashboard/')
    return render(request, 'group/create_group.html')


def join_group(request):
    error = None
    if request.method == "POST":
        code = request.POST['code']
        try:
            group = Group.objects.get(group_code=code)
            group.members.add(request.user)
            return redirect('/dashboard/')
        except Group.DoesNotExist:
            error = "Invalid group code"
    return render(request, 'group/join_group.html', {'error': error})


def group_detail(request, group_id):
    group = Group.objects.get(id=group_id)
    expenses = group.expenses.all()
    total_expense = sum(exp.amount for exp in expenses)

    return render(request, 'group/group_detail.html', {
        'group': group,
        'expenses': expenses,
        'total_expense': total_expense
    })


# =========================
# EXPENSES (WITH RECEIPT)
# =========================

def add_expense(request, group_id):
    group = Group.objects.get(id=group_id)

    if request.method == "POST":
        Expense.objects.create(
            group=group,
            paid_by=request.user,
            amount=request.POST['amount'],
            description=request.POST['description'],
            receipt=request.FILES.get('receipt')  # ✅ OPTIONAL
        )
        return redirect(f'/group/{group_id}/')

    return render(request, 'expense/add_expense.html', {'group': group})


# =========================
# SPLIT + SETTLE
# =========================

def split_bill(request, group_id):
    group = Group.objects.get(id=group_id)
    members = group.members.all()
    expenses = group.expenses.all()
    settlements_db = Settlement.objects.filter(group=group)

    total = Decimal(sum(exp.amount for exp in expenses))
    share = total / members.count() if members.count() else Decimal('0')

    balances = {}

    for member in members:
        paid = sum(exp.amount for exp in expenses if exp.paid_by == member)
        balances[member] = Decimal(paid) - share

    for s in settlements_db:
        balances[s.paid_by] += s.amount
        balances[s.paid_to] -= s.amount

    creditors = []
    debtors = []

    for user, bal in balances.items():
        if bal > 0:
            creditors.append({'user': user, 'amount': bal})
        elif bal < 0:
            debtors.append({'user': user, 'amount': abs(bal)})

    settlements = []
    i = j = 0

    while i < len(debtors) and j < len(creditors):
        d = debtors[i]
        c = creditors[j]
        amt = min(d['amount'], c['amount'])

        settlements.append({
            'from': d['user'],
            'to': c['user'],
            'amount': amt
        })

        d['amount'] -= amt
        c['amount'] -= amt

        if d['amount'] == 0:
            i += 1
        if c['amount'] == 0:
            j += 1

    return render(request, 'group/split_result.html', {
        'group': group,
        'total': total,
        'share': share,
        'settlements': settlements
    })


def settle_up(request, group_id, from_user_id, to_user_id):
    group = Group.objects.get(id=group_id)
    from_user = User.objects.get(id=from_user_id)
    to_user = User.objects.get(id=to_user_id)

    if request.method == "POST":
        Settlement.objects.create(
            group=group,
            paid_by=from_user,
            paid_to=to_user,
            amount=Decimal(request.POST['amount'])
        )
        return redirect(f'/group/{group_id}/split/')

    return render(request, 'group/settle_up.html', {
        'group': group,
        'from_user': from_user,
        'to_user': to_user
    })
