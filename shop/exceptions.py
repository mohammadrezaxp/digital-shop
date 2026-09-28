import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("shop.security")


def custom_exception_handler(exc, context):
    """
    Custom exception handler for consistent error responses.
    """
    # Log security-relevant exceptions
    if isinstance(exc, (DjangoValidationError, IntegrityError)):
        security_logger.warning(
            f"Validation/Integrity error: {exc}",
            extra={
                "path": context.get("request").path if context.get("request") else None,
                "user": (
                    str(context.get("request").user) if context.get("request") else None
                ),
                "method": (
                    context.get("request").method if context.get("request") else None
                ),
            },
        )

    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Customize error response format
        custom_response = {
            "success": False,
            "error": {
                "code": response.status_code,
                "message": _extract_error_message(response.data),
                "details": response.data if isinstance(response.data, dict) else None,
            },
        }
        response.data = custom_response
        return response

    # Handle unhandled exceptions
    if isinstance(exc, Http404):
        return Response(
            {
                "success": False,
                "error": {
                    "code": 404,
                    "message": "منبع درخواستی یافت نشد.",
                },
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, DjangoValidationError):
        return Response(
            {
                "success": False,
                "error": {
                    "code": 400,
                    "message": "داده‌های ورودی معتبر نیستند.",
                    "details": (
                        exc.message_dict if hasattr(exc, "message_dict") else str(exc)
                    ),
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, IntegrityError):
        return Response(
            {
                "success": False,
                "error": {
                    "code": 409,
                    "message": "خطای یکپارچگی داده‌ها. این مورد قبلاً ثبت شده است.",
                },
            },
            status=status.HTTP_409_CONFLICT,
        )

    # Log unhandled exceptions
    logger.exception(
        f"Unhandled exception: {exc}",
        extra={
            "path": context.get("request").path if context.get("request") else None,
            "user": (
                str(context.get("request").user) if context.get("request") else None
            ),
        },
    )

    # Generic error response
    return Response(
        {
            "success": False,
            "error": {
                "code": 500,
                "message": "خطای داخلی سرور. لطفاً بعداً تلاش کنید.",
            },
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _extract_error_message(data):
    """Extract a human-readable error message from DRF error data."""
    if isinstance(data, dict):
        # Handle field errors
        if "detail" in data:
            return str(data["detail"])
        # Handle field-specific errors
        messages = []
        for field, errors in data.items():
            if isinstance(errors, list):
                messages.append(f"{field}: {', '.join(str(e) for e in errors)}")
            else:
                messages.append(f"{field}: {errors}")
        return "; ".join(messages) if messages else "خطای اعتبارسنجی"
    elif isinstance(data, list):
        return "; ".join(str(item) for item in data)
    return str(data)
