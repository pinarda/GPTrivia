import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class AlphaNumericSpecialCharacterValidator:
    message = _("Must include alphabetical, numeric, and one special character.")
    code = "password_missing_character_classes"

    def validate(self, password, user=None):
        password = password or ""
        has_alpha = bool(re.search(r"[A-Za-z]", password))
        has_numeric = bool(re.search(r"\d", password))
        has_special = bool(re.search(r"[^A-Za-z0-9]", password))

        if has_alpha and has_numeric and has_special:
            return

        raise ValidationError(self.message, code=self.code)

    def get_help_text(self):
        return self.message
