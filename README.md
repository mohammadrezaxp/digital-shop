# Digital Shop

**A Django storefront and REST API for digital products, subscriptions, orders, and customer wallets.**

[API routes](config/urls.py) · [Domain models](shop/models.py) · [Checkout service](shop/services.py) · [Tests](shop/test_regressions.py) · [CI](https://github.com/mohammadrezaxp/digital-shop/actions/workflows/ci.yml)

Digital Shop brings a browsable catalog and a customer API into one Django application. Its backend covers product variants, scoped coupons, wallet checkout, cancellation refunds, subscription delivery, and authentication with optional TOTP two-factor verification.

## What is implemented

| Area | Behavior |
| --- | --- |
| Catalog | Active products and categories, product variants, search, filtering, ordering, and featured products |
| Authentication | JWT access/refresh pairs, refresh rotation, password validation, login audit records, and account lockout |
| Two-factor authentication | TOTP setup, verification, disable, and one-time backup-code consumption |
| Orders | Validated line items, aggregate stock checks, transactional stock reservations, and server-calculated totals |
| Wallet checkout | Available-balance checks, purchase records, and cancellation refunds without repeat credits |
| Coupons | Validity dates, usage limits, per-user usage, and product/category eligibility |
| Subscriptions | Delivery-linked subscription creation and scheduled expiration |
| Customer account | Profile, addresses, notifications, wallet history, and dashboard data |

This is a development and portfolio application. External card/gateway selections create pending orders; they do not charge a payment provider. Automatic renewal billing and automated digital fulfillment are not provided by the expiration task.

## Stack

Python 3.12+ · Django 6.1 · Django REST Framework · SimpleJWT · PostgreSQL/SQLite · Celery/Redis · drf-spectacular · pytest

Exact dependency constraints live in [requirements.txt](requirements.txt). Docker and CI use Python 3.12.

## Run locally

```bash
git clone https://github.com/mohammadrezaxp/digital-shop.git
cd digital-shop
python -m venv .venv
```

Activate the environment using the command for your shell:

| Shell | Command |
| --- | --- |
| macOS/Linux | `source .venv/bin/activate` |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |

```bash
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` (`cp .env.example .env` in Bash or `Copy-Item .env.example .env` in PowerShell). Replace `SECRET_KEY` with a generated local key, keep `DEBUG=True`, and use `USE_POSTGRES=False` for SQLite.

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Optional catalog fixtures: `python manage.py create_sample_data`. The fixture command creates a demo administrator with known credentials; use it only in an isolated development database.

Open the [storefront](http://127.0.0.1:8000/), [Swagger UI](http://127.0.0.1:8000/api/docs/), or [admin](http://127.0.0.1:8000/admin/).

## API walkthrough

Examples below use Bash/curl. Obtain product IDs from the catalog; product detail routes use **slugs**, while order lines use numeric IDs.

```bash
curl 'http://127.0.0.1:8000/api/products/?search=gift&ordering=price'

curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"your-user","password":"your-password"}'
```

Login returns `access`, `refresh`, and `user`. If 2FA is enabled, include `two_factor_code` in the same request. The compatibility endpoint `/api/auth/2fa/verify/` also requires the password; a second factor alone cannot obtain tokens.

```bash
curl -X POST http://127.0.0.1:8000/api/orders/ \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"product_id":1,"quantity":1}],"payment_method":"wallet"}'
```

A successful wallet order returns HTTP 201 with status `paid`. Insufficient balance or stock returns a validation error and rolls back checkout. For a variant, also supply `variant_id`. Card/gateway orders remain `pending` until a separately implemented payment integration confirms them.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/products/`, `/api/products/{slug}/`, `/api/categories/` | Public catalog |
| POST | `/api/auth/register/`, `/api/auth/login/` | Register or log in |
| POST | `/api/auth/token/refresh/` | Rotate refresh token |
| GET/PATCH | `/api/auth/profile/` | Current user's profile |
| GET/POST | `/api/auth/2fa/setup/` | Start setup or confirm a TOTP code |
| POST | `/api/auth/2fa/disable/`, `/api/auth/2fa/backup-codes/` | Manage 2FA with a valid code |
| GET/POST | `/api/orders/` | List own orders or check out |
| POST | `/api/orders/{id}/cancel/` | Cancel an eligible order |
| GET | `/api/wallet/`, `/api/wallet/transactions/` | Wallet and financial history |
| POST | `/api/coupons/validate/` | Preview a coupon; send items for scoped coupons |
| GET | `/api/subscriptions/`, `/api/dashboard/` | Customer account data |
| GET | `/health/`, `/api/schema/`, `/api/docs/`, `/api/redoc/` | Health and API documentation |

Order totals, payment status, and delivery state are server-managed. Cancellation restores inventory once and refunds eligible wallet payments once. Delivered orders and confirmed external payments require a manual refund process. Deleting an order through the customer API cancels it while retaining the record.

## Configuration and background work

See [.env.example](.env.example) and [settings](config/settings.py) for the complete configuration.

| Variable | Local setup |
| --- | --- |
| `SECRET_KEY` | Generate a unique value; never reuse the example |
| `DEBUG`, `ALLOWED_HOSTS` | `True` and localhost for development |
| `USE_POSTGRES`, `POSTGRES_*` | Enable PostgreSQL and supply connection details when needed |
| `REDIS_URL`, `CELERY_BROKER_URL` | Redis service for workers |
| `JWT_ACCESS_LIFETIME_MINUTES`, `JWT_REFRESH_LIFETIME_DAYS` | Token lifetimes |
| `CORS_ALLOWED_ORIGINS` | Explicit origins for a separate frontend |

```bash
# Separate terminals, with Redis running:
celery -A config worker -l info
celery -A config beat -l info
```

Beat schedules `shop.tasks.expire_subscriptions` hourly. Run a single Beat instance per environment. Windows users can run the workers through Docker or WSL.

The [Compose file](docker-compose.yml) includes web, PostgreSQL, Redis, worker, and Beat services. Review its environment and demo-seeding startup command before use. It is a development starting point, not an unattended production deployment configuration.

## Validate changes

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
pytest -v
pytest --cov=shop --cov-report=term-missing
```

Tests cover authentication, 2FA, password validation, stock and quantity validation, coupon eligibility, wallet rollback/refunds, and delivery-linked subscriptions. CI defines lint, database-backed test, and Docker build jobs. A workflow definition is not a claim that the latest run passed; inspect the linked run history.

## Code map

```text
config/              Settings, URL routing, WSGI/ASGI, and Celery app
shop/models.py       Catalog, orders, wallets, coupons, and subscriptions
shop/serializers.py  Request validation and response schemas
shop/services.py     Checkout, payment, and cancellation transactions
shop/views.py        API endpoints and authentication
shop/signals.py      Wallet posting and delivery lifecycle hooks
shop/tasks.py        Scheduled subscription expiration
shop/test_regressions.py  Regression tests for repaired flows
templates/           Storefront pages
```

## Operational boundaries

- Use PostgreSQL when validating concurrent checkout. SQLite does not provide equivalent row locking.
- Configure HTTPS, hosts, origins, secret management, backups, and static/media serving before deployment.
- TOTP secrets and backup codes currently reside in database fields; assess encryption and hashed recovery-code storage before handling real customer accounts.
- The JWT API is the reference for account operations; storefront templates do not imply a complete browser checkout integration.
- If installation fails, confirm the active Python version and dependency constraints before changing package versions.

## Contributing

Open an issue with reproduction steps, or submit a focused pull request with a regression test. Do not include credentials, token values, or customer data in reports. For private security reports, contact [the maintainer](mailto:m.mahmoudi.xp@gmail.com).
