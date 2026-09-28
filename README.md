# Digital Shop — Django REST API

A production-ready Django REST API backend for a digital goods marketplace (gift cards, subscriptions, software licenses, VPN, streaming). Built with Django 5.2+, DRF 3.18+, JWT authentication, 2FA, and comprehensive security hardening.

## Features

- **Authentication & Authorization**
  - JWT (djangorestframework-simplejwt) with sliding tokens (30min access, 7d refresh)
  - Token rotation + blacklist after rotation
  - TOTP-based 2FA (pyotp) with QR code setup and 10 backup codes
  - Login lockout after 5 failed attempts (30-minute cooldown)
  - Comprehensive audit logging via `LoginAttempt` model

- **Security**
  - Custom password validators: special characters, no common patterns, no personal info
  - Argon2 available (installed), PBKDF2 default
  - Security headers: COOP, COEP, Referrer-Policy, Permissions-Policy, X-Frame-Options, X-Content-Type-Options
  - Content Security Policy (CSP) configured
  - Rate limiting (throttle scopes: login, register, api, burst)
  - Custom exception handler with security logging
  - No hardcoded secrets — all via `.env` (python-decouple)

- **Data Models** (15 models)
  - `User` (extended AbstractUser with 2FA, phone, avatar, login tracking)
  - `Category`, `Product`, `ProductVariant` (digital delivery types: code, file, account, link, manual)
  - `Order`, `OrderItem` (tracking, delivery status)
  - `Subscription` (recurring products with auto-renewal)
  - `Wallet`, `WalletTransaction` (balance, blocked balance, transaction history)
  - `Coupon`, `CouponUsage` (percent/fixed, min/max, category/product scoping)
  - `Address`, `Notification`, `SiteSettings`, `LoginAttempt`

- **API**
  - RESTful ViewSets for all resources
  - Pagination, filtering, search, ordering
  - OpenAPI 3.1 schema via drf-spectacular
  - Swagger UI (`/api/docs/`) + ReDoc (`/api/redoc/`)
  - Health check endpoint (`/health/`) for Docker/load balancers

- **Admin**
  - Full Django admin registration with custom fieldsets
  - Read-only audit fields (2FA, login tracking)

- **Deployment**
  - Multi-stage Dockerfile (non-root user, gunicorn, health check)
  - docker-compose.yml (PostgreSQL, Redis, Web)
  - GitHub Actions CI (lint, test, build)

## Quick Start

### Local Development

```bash
# Clone and enter
cd Digital_Shop

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run migrations and seed data
python manage.py migrate
python manage.py create_sample_data

# Create superuser (admin/admin123)
python manage.py createsuperuser --username admin --email admin@digitalshop.ir --noinput
# Then set password:
python manage.py shell -c "from django.contrib.auth import get_user_model; u=get_user_model().objects.get(username='admin'); u.set_password('admin123'); u.save()"

# Start server
python manage.py runserver 127.0.0.1:8000
```

### Docker

```bash
# Development
docker-compose up --build

# Production (set env vars first)
docker-compose -f docker-compose.yml up -d --build
```

## Environment Variables

See `.env.example` for all options. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Debug mode | `False` |
| `SECRET_KEY` | Django secret key | *required* |
| `ALLOWED_HOSTS` | Comma-separated hosts | `localhost,127.0.0.1` |
| `USE_POSTGRES` | Use PostgreSQL instead of SQLite | `False` |
| `POSTGRES_*` | PostgreSQL connection | — |
| `REDIS_URL` | Redis for caching/throttle | `redis://localhost:6379/0` |
| `JWT_*` | JWT lifetimes | 30min/7d |
| `CORS_ALLOWED_ORIGINS` | CORS origins | `http://localhost:3000` |
| `CSRF_TRUSTED_ORIGINS` | CSRF trusted origins | `http://localhost:8000` |

## API Endpoints

### Public
- `GET /api/products/` — List products (filter: category, search, ordering)
- `GET /api/products/{id}/` — Product detail
- `GET /api/categories/` — List categories
- `GET /api/settings/` — Site settings

### Authentication
- `POST /api/auth/login/` — Login (returns access/refresh tokens)
- `POST /api/auth/refresh/` — Refresh access token
- `POST /api/auth/register/` — Register new user
- `POST /api/auth/verify/` — Verify token

### 2FA (authenticated)
- `GET /api/auth/2fa/setup/` — Get TOTP secret + QR code
- `POST /api/auth/2fa/setup/` — Verify code & enable 2FA
- `POST /api/auth/2fa/disable/` — Disable 2FA (requires password)
- `POST /api/auth/2fa/verify/` — Verify 2FA code (login-time)
- `GET /api/auth/2fa/backup-codes/` — Get backup codes
- `POST /api/auth/2fa/backup-codes/` — Regenerate backup codes

### Protected (require Bearer token)
- `GET /api/dashboard/` — User dashboard stats
- `GET /api/profile/` — User profile
- `GET /api/wallet/` — Wallet balance
- `GET /api/wallet/transactions/` — Transaction history
- `GET /api/orders/` — User orders
- `GET /api/orders/{id}/` — Order detail
- `POST /api/orders/` — Create order
- `GET /api/subscriptions/` — User subscriptions
- `GET /api/addresses/` — User addresses
- `GET /api/notifications/` — User notifications
- `POST /api/coupons/validate/` — Validate coupon code

### Health & Docs
- `GET /health/` — Health check (DB connectivity)
- `GET /api/schema/` — OpenAPI JSON schema
- `GET /api/docs/` — Swagger UI
- `GET /api/redoc/` — ReDoc

## Testing

```bash
# Run all tests
pytest shop/tests.py -v

# With coverage
pytest shop/tests.py --cov=shop --cov-report=term-missing
```

19 tests covering:
- Password validators (special chars, common patterns, personal info)
- 2FA flow (setup, verify, disable, backup codes)
- Login lockout mechanism
- Serializer validation
- Model relationships
- Coupon validation

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`):
1. **Lint** — black, isort, flake8
2. **Test** — pytest with PostgreSQL + Redis services
3. **Build** — Docker image (on push to main)

## Project Structure

```
Digital_Shop/
├── config/                 # Django project settings
│   ├── settings.py         # Main settings (546 lines, security-hardened)
│   ├── urls.py             # Root URL config
│   └── wsgi.py
├── shop/                   # Main app
│   ├── models.py           # 15 models (511 lines)
│   ├── views.py            # ViewSets + auth endpoints (485 lines)
│   ├── serializers.py      # DRF serializers (179 lines)
│   ├── validators.py       # Custom password validators
│   ├── middleware.py       # Security headers middleware
│   ├── exceptions.py       # Custom exception handler
│   ├── signals.py          # Wallet creation, subscription handling
│   ├── admin.py            # Django admin registration
│   ├── apps.py             # AppConfig with signals
│   ├── tests.py            # 19 tests (363 lines)
│   └── management/commands/create_sample_data.py  # Seed data
├── templates/
│   └── base.html           # Tailwind + RTL base template
├── static/                 # Static assets
├── .github/workflows/ci.yml
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── pytest.ini
└── manage.py
```

## Default Credentials (after create_sample_data)

- **Admin**: `admin` / `admin123`
- **Sample Products**: 13 products across 5 categories (Gaming, AI, VPN, Streaming, Software)
- **Coupons**: `WELCOME10` (10%), `SAVE20` (20%), `VIP30` (30%)

## Security Notes for Production

1. **Rotate `SECRET_KEY`** — generate with `django.core.management.utils.get_random_secret_key()`
2. **Set `DEBUG=False`** and configure `ALLOWED_HOSTS`
3. **Use PostgreSQL** — set `USE_POSTGRES=True` and provide `POSTGRES_*` vars
4. **Enable HTTPS** — set `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`
5. **Use Argon2** — add to `PASSWORD_HASHERS` in settings (argon2-cffi installed)
6. **Encrypt 2FA secrets at rest** — consider `django-encrypted-model-fields` for `two_factor_secret` and `backup_codes`
7. **Configure CSP nonces/hashes** — replace `'unsafe-inline'` for Tailwind CDN
8. **Set up email** — configure `EMAIL_*` for password reset, verification flows
9. **Monitor `logs/security.log`** — audit trail for auth events

## License

MIT — free for portfolio and commercial use.