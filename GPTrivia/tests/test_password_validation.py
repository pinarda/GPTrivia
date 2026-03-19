from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.test import TestCase
from django.urls import reverse


class PasswordValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alex", password="OldPassword1!")
        self.client.force_login(self.user)

    def test_password_change_page_shows_updated_requirements(self):
        response = self.client.get(reverse("password_change"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your password must contain at least 8 characters.")
        self.assertContains(response, "Must include alphabetical, numeric, and one special character.")
        self.assertNotContains(response, "Your password can’t be too similar to your other personal information.")
        self.assertNotContains(response, "Your password can’t be a commonly used password.")
        self.assertNotContains(response, "Your password can’t be entirely numeric.")

    def test_password_requires_alpha_numeric_and_special_character(self):
        with self.assertRaises(ValidationError):
            validate_password("abcdefgh", user=self.user)

        with self.assertRaises(ValidationError):
            validate_password("abc12345", user=self.user)

        with self.assertRaises(ValidationError):
            validate_password("abc!defg", user=self.user)

        validate_password("abc1234!", user=self.user)
