import io
import tempfile
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from GPTrivia.models import GPTriviaRound, Profile
from GPTrivia.profile_media import get_profile_avatar_url, get_profile_picture_url
from GPTrivia.views import _build_player_icon_map


class ProfileIconTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.temp_media.cleanup()

    def _make_uploaded_image(self, color=(200, 40, 90)):
        image_buffer = io.BytesIO()
        Image.new('RGB', (120, 120), color).save(image_buffer, format='JPEG')
        image_buffer.seek(0)
        return SimpleUploadedFile('profile.jpg', image_buffer.getvalue(), content_type='image/jpeg')

    def _make_large_uploaded_image(self, color=(80, 120, 220)):
        image_buffer = io.BytesIO()
        Image.new('RGB', (1800, 1800), color).save(image_buffer, format='JPEG')
        image_buffer.seek(0)
        return SimpleUploadedFile('profile-large.jpg', image_buffer.getvalue(), content_type='image/jpeg')

    def _make_split_uploaded_image(self):
        image_buffer = io.BytesIO()
        image = Image.new('RGB', (200, 100), (220, 20, 60))
        for x in range(100, 200):
            for y in range(0, 100):
                image.putpixel((x, y), (25, 90, 210))
        image.save(image_buffer, format='JPEG')
        image_buffer.seek(0)
        return SimpleUploadedFile('profile-wide.jpg', image_buffer.getvalue(), content_type='image/jpeg')

    def _make_profile_round_history(self, creator='Alex', total_rounds=50):
        base_date = date(2025, 1, 1)
        GPTriviaRound.objects.bulk_create([
            GPTriviaRound(
                creator=creator,
                title=f'Round {index + 1}',
                major_category='Science',
                minor_category1='General',
                minor_category2='Facts',
                date=base_date + timedelta(days=index),
                round_number=index + 1,
                max_score=10,
                score_alex=8,
            )
            for index in range(total_rounds)
        ])

    def test_profile_save_generates_a_50px_icon_for_custom_photos(self):
        user = User.objects.create_user(username='Alex', password='pw')
        profile = user.profile
        profile.profile_picture = self._make_uploaded_image()
        profile.save()

        profile.refresh_from_db()

        self.assertTrue(profile.profile_icon.name)
        self.assertTrue(profile.profile_icon.name.endswith('_icon.png'))

        with Image.open(profile.profile_icon.path) as icon_image:
            self.assertEqual(icon_image.size, (50, 50))
            self.assertEqual(icon_image.mode, 'RGBA')

    def test_scoresheet_view_uses_profile_picture_without_generating_missing_icon(self):
        user = User.objects.create_user(username='Alex', password='pw')
        profile = user.profile
        profile.profile_picture = self._make_uploaded_image(color=(20, 120, 220))
        profile.save()

        # Simulate an older uploaded profile that predates the icon field being populated.
        profile.profile_icon.delete(save=False)
        type(profile).objects.filter(pk=profile.pk).update(profile_icon='')
        profile.refresh_from_db()

        self.client.force_login(user)
        with patch.object(Profile, 'ensure_profile_icon') as ensure_profile_icon:
            response = self.client.get(reverse('scoresheet_new'))

        self.assertEqual(response.status_code, 200)
        ensure_profile_icon.assert_not_called()
        self.assertContains(response, 'scoresheet-player-icons')
        self.assertContains(response, get_profile_avatar_url(profile))
        self.assertContains(response, 'Alex')

    def test_player_icon_map_falls_back_to_profile_picture_when_icon_is_unavailable(self):
        user = User.objects.create_user(username='Alex', password='pw')
        profile = user.profile
        profile.profile_picture = self._make_uploaded_image(color=(20, 120, 220))
        profile.save()
        profile.profile_icon.delete(save=False)
        type(profile).objects.filter(pk=profile.pk).update(profile_icon='')
        profile.refresh_from_db()

        with patch.object(Profile, 'ensure_profile_icon') as ensure_profile_icon:
            icon_map = _build_player_icon_map()

        ensure_profile_icon.assert_not_called()
        self.assertIn('Alex', icon_map)
        self.assertEqual(icon_map['Alex'], get_profile_avatar_url(profile))

    def test_upload_profile_picture_crops_selected_square_region_and_updates_color_and_theme(self):
        user = User.objects.create_user(username='Alex', password='pw')
        self.client.force_login(user)

        response = self.client.post(
            reverse('upload_profile_picture'),
            {
                'profile_picture': self._make_split_uploaded_image(),
                'profile_color': '#123abc',
                'profile_page_chrome_color': '#654321',
                'profile_page_trivia_color_one': '#111111',
                'profile_page_trivia_color_two': '#222222',
                'profile_page_trivia_color_three': '#333333',
                'profile_page_theme': 'light',
                'site_theme': 'light',
                'crop_x': '100',
                'crop_y': '0',
                'crop_size': '100',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('player_profile', args=['Alex']))

        user.profile.refresh_from_db()
        self.assertEqual(user.profile.profile_color, '#123abc')
        self.assertEqual(user.profile.profile_page_chrome_color, '#654321')
        self.assertEqual(user.profile.profile_page_trivia_color_one, '#111111')
        self.assertEqual(user.profile.profile_page_trivia_color_two, '#222222')
        self.assertEqual(user.profile.profile_page_trivia_color_three, '#333333')
        self.assertEqual(user.profile.profile_page_theme, 'light')
        self.assertEqual(user.profile.site_theme, 'light')
        self.assertRegex(
            user.profile.profile_picture.name,
            r'^profile_pics/profile-wide_[0-9a-f]{12}_cropped\.jpg$',
        )

        with Image.open(user.profile.profile_picture.path) as cropped_image:
            self.assertEqual(cropped_image.size, (100, 100))
            center_pixel = cropped_image.convert('RGB').getpixel((50, 50))
            self.assertGreater(center_pixel[2], center_pixel[0])

    def test_upload_profile_picture_downsizes_large_uploads(self):
        user = User.objects.create_user(username='Alex', password='pw')
        self.client.force_login(user)

        response = self.client.post(
            reverse('upload_profile_picture'),
            {
                'profile_picture': self._make_large_uploaded_image(),
                'profile_color': '#123abc',
                'profile_page_chrome_color': '#654321',
                'profile_page_trivia_color_one': '#111111',
                'profile_page_trivia_color_two': '#222222',
                'profile_page_trivia_color_three': '#333333',
                'profile_page_theme': 'light',
                'site_theme': 'light',
                'crop_x': '0',
                'crop_y': '0',
                'crop_size': '1800',
            },
        )

        self.assertEqual(response.status_code, 302)
        user.profile.refresh_from_db()

        with Image.open(user.profile.profile_picture.path) as saved_image:
            self.assertEqual(saved_image.size, (720, 720))

    def test_profile_view_shows_round_analysis_opt_in_button_and_toggle_updates_profile(self):
        user = User.objects.create_user(username='Alex', password='pw')
        self.client.force_login(user)

        response = self.client.get(reverse('player_profile', args=['Alex']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enable Round Analysis')
        self.assertContains(response, 'OpenAI response storage is disabled for these requests.')

        toggle_response = self.client.post(
            reverse('toggle_round_analysis_opt_in', args=['Alex']),
            {'round_analysis_opt_in': '1'},
        )

        self.assertEqual(toggle_response.status_code, 302)
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.round_analysis_opt_in)

    def test_scoresheet_view_applies_saved_light_theme(self):
        user = User.objects.create_user(username='Alex', password='pw')
        profile = user.profile
        profile.site_theme = 'light'
        profile.save()

        self.client.force_login(user)
        response = self.client.get(reverse('scoresheet_new'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-profile-theme="light"')
        self.assertContains(response, '--scoresheet-surface: #f4f1e8;')

    def test_scoresheet_view_embeds_profile_color_overrides(self):
        user = User.objects.create_user(username='Alex', password='pw')
        profile = user.profile
        profile.profile_color = '#123abc'
        profile.save()

        self.client.force_login(user)
        response = self.client.get(reverse('scoresheet_new'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'scoresheet-player-colors')
        self.assertContains(response, '#123abc')

    def test_profile_view_applies_saved_profile_page_color_customizations(self):
        user = User.objects.create_user(username='Alex', password='pw')
        self._make_profile_round_history()
        profile = user.profile
        profile.profile_page_chrome_color = '#654321'
        profile.profile_page_trivia_color_one = '#111111'
        profile.profile_page_trivia_color_two = '#222222'
        profile.profile_page_trivia_color_three = '#333333'
        profile.save()

        self.client.force_login(user)
        response = self.client.get(reverse('player_profile', args=['Alex']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '--profile-page-chrome-color: #654321;')
        self.assertContains(response, '--profile-page-trivia-color-one: #111111;')
        self.assertContains(response, '--profile-page-trivia-color-two: #222222;')
        self.assertContains(response, '--profile-page-trivia-color-three: #333333;')
        self.assertContains(response, 'Player Color')

    def test_profile_view_uses_uploaded_profile_picture_url(self):
        user = User.objects.create_user(username='Alex', password='pw')
        self._make_profile_round_history()
        profile = user.profile
        profile.profile_picture = self._make_uploaded_image(color=(30, 30, 180))
        profile.save()
        profile.refresh_from_db()

        self.client.force_login(user)
        response = self.client.get(reverse('player_profile', args=['Alex']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, get_profile_picture_url(profile))

    def test_profile_picture_media_endpoint_serves_uploaded_picture(self):
        user = User.objects.create_user(username='Alex', password='pw')
        profile = user.profile
        profile.profile_picture = self._make_uploaded_image(color=(30, 30, 180))
        profile.save()

        self.client.force_login(user)
        response = self.client.get(get_profile_picture_url(profile))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('image/'))

    def test_profile_avatar_media_endpoint_serves_profile_icon(self):
        user = User.objects.create_user(username='Alex', password='pw')
        profile = user.profile
        profile.profile_picture = self._make_uploaded_image(color=(80, 20, 220))
        profile.save()

        self.client.force_login(user)
        response = self.client.get(get_profile_avatar_url(profile))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('image/'))

    def test_profile_view_defaults_page_color_inputs_to_profile_palette(self):
        user = User.objects.create_user(username='Alex', password='pw')
        self._make_profile_round_history()

        self.client.force_login(user)
        response = self.client.get(reverse('player_profile', args=['Alex']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="profile-page-chrome-input"')
        self.assertContains(response, 'value="#2d3047"')
        self.assertContains(response, 'id="profile-trivia-color-one-input"')
        self.assertContains(response, 'value="#588b8b"')
        self.assertContains(response, 'id="profile-trivia-color-two-input"')
        self.assertContains(response, 'value="#ffd5c2"')
        self.assertContains(response, 'id="profile-trivia-color-three-input"')
        self.assertContains(response, 'value="#c8553d"')

    def test_profile_view_uses_viewed_players_profile_page_theme(self):
        owner = User.objects.create_user(username='Alex', password='pw')
        viewer = User.objects.create_user(username='Megan', password='pw')
        self._make_profile_round_history()
        owner.profile.profile_page_theme = 'light'
        owner.profile.save()
        viewer.profile.site_theme = 'default'
        viewer.profile.save()

        self.client.force_login(viewer)
        response = self.client.get(reverse('player_profile', args=['Alex']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-profile-theme="light"')
