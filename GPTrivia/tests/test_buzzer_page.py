from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from GPTrivia.consumers import _serialize_button_results, _upsert_button_press


class BuzzerPageTests(TestCase):
    def test_buzzer_page_uses_non_login_name_field_markup(self):
        response = self.client.get(reverse('button_page'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="buzzer-name"')
        self.assertContains(response, 'name="display_name"')
        self.assertContains(response, 'autocomplete="off"')
        self.assertNotContains(response, 'id="username"')
        self.assertContains(response, 'id="button-placements"')


class ButtonRankingHelperTests(SimpleTestCase):
    def test_upsert_button_press_orders_by_reaction_time(self):
        presses = []
        presses = _upsert_button_press(
            presses,
            username='Alex',
            sender_id='alpha',
            reaction_ms=142.0,
        )
        presses = _upsert_button_press(
            presses,
            username='Jamie',
            sender_id='beta',
            reaction_ms=155.5,
        )
        presses = _upsert_button_press(
            presses,
            username='Morgan',
            sender_id='gamma',
            reaction_ms=147.25,
        )

        payload = _serialize_button_results(presses)

        self.assertEqual(payload['winner']['username'], 'Alex')
        self.assertEqual(
            [entry['username'] for entry in payload['standings']],
            ['Alex', 'Morgan', 'Jamie'],
        )
        self.assertEqual(payload['standings'][0]['miss_ms'], 0.0)
        self.assertEqual(payload['standings'][1]['miss_ms'], 5.25)
        self.assertEqual(payload['standings'][2]['miss_ms'], 13.5)

    def test_upsert_button_press_keeps_fastest_press_for_same_sender(self):
        presses = _upsert_button_press(
            [],
            username='Alex',
            sender_id='alpha',
            reaction_ms=200.0,
        )
        presses = _upsert_button_press(
            presses,
            username='Alex',
            sender_id='alpha',
            reaction_ms=215.0,
        )
        presses = _upsert_button_press(
            presses,
            username='Alex',
            sender_id='alpha',
            reaction_ms=180.0,
        )

        payload = _serialize_button_results(presses)

        self.assertEqual(len(payload['standings']), 1)
        self.assertEqual(payload['winner']['reaction_ms'], 180.0)
