from django.test import TestCase
from django.urls import reverse


class BuzzerPageTests(TestCase):
    def test_buzzer_page_uses_non_login_name_field_markup(self):
        response = self.client.get(reverse('button_page'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="buzzer-name"')
        self.assertContains(response, 'name="display_name"')
        self.assertContains(response, 'autocomplete="off"')
        self.assertNotContains(response, 'id="username"')
