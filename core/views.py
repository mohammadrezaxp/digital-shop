from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from .forms import ProfileForm, RegisterForm

# Display-only data. Replace with DRF-backed models after implementing the wallet ledger.
DEMO_TRANSACTIONS = [
    {'name': 'Design subscription', 'date': 'Oct 08, 2026', 'amount': '-$24.00', 'kind': 'out', 'status': 'Completed'},
    {'name': 'Alex Morgan', 'date': 'Oct 07, 2026', 'amount': '+$180.00', 'kind': 'in', 'status': 'Completed'},
    {'name': 'Coffee Studio', 'date': 'Oct 06, 2026', 'amount': '-$12.50', 'kind': 'out', 'status': 'Completed'},
    {'name': 'Jordan Lee', 'date': 'Oct 05, 2026', 'amount': '+$90.00', 'kind': 'in', 'status': 'Completed'},
]

def home(request):
    return render(request, 'pages/home.html')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('dashboard')
    return render(request, 'accounts/login.html', {'form': form})

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('dashboard')
    return render(request, 'accounts/register.html', {'form': form})

@require_POST
def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def dashboard(request):
    return render(request, 'wallet/dashboard.html', {'transactions': DEMO_TRANSACTIONS[:3]})

@login_required
def wallet(request):
    return render(request, 'wallet/wallet.html')

@login_required
def transfer(request):
    # IMPORTANT: Never mutate balances here. Add atomic ledger logic in the backend first.
    return render(request, 'wallet/transfer.html')

@login_required
def transactions(request):
    return render(request, 'wallet/transactions.html', {'transactions': DEMO_TRANSACTIONS})

@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')
    return render(request, 'accounts/profile.html', {'form': form})
