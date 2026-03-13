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
