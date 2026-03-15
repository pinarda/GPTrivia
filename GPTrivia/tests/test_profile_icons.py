import io
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image


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

    def _make_split_uploaded_image(self):
        image_buffer = io.BytesIO()
        image = Image.new('RGB', (200, 100), (220, 20, 60))
        for x in range(100, 200):
            for y in range(0, 100):
                image.putpixel((x, y), (25, 90, 210))
        image.save(image_buffer, format='JPEG')
        image_buffer.seek(0)
        return SimpleUploadedFile('profile-wide.jpg', image_buffer.getvalue(), content_type='image/jpeg')

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

    def test_scoresheet_view_embeds_generated_player_icon_map(self):
        user = User.objects.create_user(username='Alex', password='pw')
        profile = user.profile
        profile.profile_picture = self._make_uploaded_image(color=(20, 120, 220))
        profile.save()

        # Simulate an older uploaded profile that predates the icon field being populated.
        profile.profile_icon.delete(save=False)
        type(profile).objects.filter(pk=profile.pk).update(profile_icon='')

        self.client.force_login(user)
        response = self.client.get(reverse('scoresheet_new'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'scoresheet-player-icons')
        self.assertContains(response, 'profile_icons')
        self.assertContains(response, 'Alex')

    def test_upload_profile_picture_crops_selected_square_region_and_updates_color_and_theme(self):
        user = User.objects.create_user(username='Alex', password='pw')
        self.client.force_login(user)

        response = self.client.post(
            reverse('upload_profile_picture'),
            {
                'profile_picture': self._make_split_uploaded_image(),
                'profile_color': '#123abc',
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
        self.assertEqual(user.profile.site_theme, 'light')

        with Image.open(user.profile.profile_picture.path) as cropped_image:
            self.assertEqual(cropped_image.size, (100, 100))
            center_pixel = cropped_image.convert('RGB').getpixel((50, 50))
            self.assertGreater(center_pixel[2], center_pixel[0])

    def test_scoresheet_view_applies_saved_light_theme(self):
        user = User.objects.create_user(username='Alex', password='pw')
        profile = user.profile
        profile.site_theme = 'light'
        profile.save()

        self.client.force_login(user)
        response = self.client.get(reverse('scoresheet_new'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-profile-theme="light"')
        self.assertContains(response, '--scoresheet-surface: #eef2f5;')

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
