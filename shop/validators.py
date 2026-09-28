import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class SpecialCharacterValidator:
    """
    Validate that password contains at least one special character.
    """

    def __init__(self, special_chars=None):
        self.special_chars = special_chars or r"!@#$%^&*()_+-=[]{}|;:,.<>?/~`"

    def validate(self, password, user=None):
        if not any(c in self.special_chars for c in password):
            raise ValidationError(
                _("رمز عبور باید حداقل یک کاراکتر خاص (%(chars)s) داشته باشد."),
                code="password_no_special_char",
                params={"chars": self.special_chars},
            )

    def get_help_text(self):
        return _("رمز عبور باید حداقل یک کاراکتر خاص داشته باشد.")


class NoCommonPatternsValidator:
    """
    Validate that password doesn't contain common patterns.
    """

    COMMON_PATTERNS = [
        r"(.)\1{2,}",  # 3+ repeated characters
        r"123|234|345|456|567|678|789|890",  # Sequential numbers
        r"abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz",  # Sequential letters
        r"qwerty|asdfgh|zxcvbn",  # Keyboard patterns
    ]

    def validate(self, password, user=None):
        password_lower = password.lower()
        for pattern in self.COMMON_PATTERNS:
            if re.search(pattern, password_lower):
                raise ValidationError(
                    _("رمز عبور شامل الگوهای رایج و قابل حدس است."),
                    code="password_common_pattern",
                )

    def get_help_text(self):
        return _("از الگوهای رایج در رمز عبور خود استفاده نکنید.")


class AttributeSimilarityValidatorExtended:
    """
    Extended similarity validator that checks more user attributes.
    """

    def __init__(self, user_attributes=None, max_similarity=0.7):
        self.user_attributes = user_attributes or [
            "username",
            "email",
            "first_name",
            "last_name",
            "phone",
        ]
        self.max_similarity = max_similarity

    def validate(self, password, user=None):
        if not user:
            return

        from difflib import SequenceMatcher

        for attr in self.user_attributes:
            value = getattr(user, attr, None)
            if value and len(value) >= 3:
                # Check substrings of the password against the attribute
                for i in range(len(password) - len(value) + 1):
                    substring = password[i : i + len(value)]
                    similarity = SequenceMatcher(
                        None, substring.lower(), value.lower()
                    ).ratio()
                    if similarity > self.max_similarity:
                        raise ValidationError(
                            _("رمز عبور شما خیلی شبیه به %(attribute)s شماست."),
                            code="password_too_similar",
                            params={"attribute": attr},
                        )

    def get_help_text(self):
        return _("رمز عبور نباید شبیه به اطلاعات شخصی شما باشد.")


class NoPersonalInfoValidator:
    """
    Validate that password doesn't contain personal information.
    """

    def validate(self, password, user=None):
        if not user:
            return

        password_lower = password.lower()
        personal_fields = ["username", "email", "first_name", "last_name", "phone"]

        for field in personal_fields:
            value = getattr(user, field, None)
            if value and len(value) >= 3:
                if value.lower() in password_lower:
                    raise ValidationError(
                        _("رمز عبور نباید شامل %(field)s شما باشد."),
                        code="password_contains_personal_info",
                        params={"field": field},
                    )

    def get_help_text(self):
        return _("رمز عبور نباید شامل اطلاعات شخصی شما باشد.")
