from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add security headers to all responses.
    """

    def process_response(self, request, response):
        # Cross-Origin Opener Policy
        response["Cross-Origin-Opener-Policy"] = getattr(
            settings, "SECURE_CROSS_ORIGIN_OPENER_POLICY", "same-origin"
        )

        # Cross-Origin Embedder Policy
        response["Cross-Origin-Embedder-Policy"] = getattr(
            settings, "SECURE_CROSS_ORIGIN_EMBEDDER_POLICY", "require-corp"
        )

        # Referrer Policy
        response["Referrer-Policy"] = getattr(
            settings, "SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin"
        )

        # Permissions Policy
        permissions_policy = getattr(settings, "PERMISSIONS_POLICY", {})
        if permissions_policy:
            policy_parts = [
                f"{key}={value}" for key, value in permissions_policy.items()
            ]
            response["Permissions-Policy"] = ", ".join(policy_parts)

        # Remove server header
        if "Server" in response:
            del response["Server"]

        # Cache control for sensitive endpoints
        if request.path.startswith("/api/auth/") or request.path.startswith(
            "/api/wallet/"
        ):
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

        return response
