from django.db import models
import jsonfield
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.files.base import ContentFile
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageDraw, ImageOps


PROFILE_ICON_SIZE = (50, 50)

# Signal handlers
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics', default='./default.jpg')
    profile_icon = models.ImageField(upload_to='profile_icons', blank=True, default='')
    profile_color = models.CharField(max_length=7, blank=True, default='')

    def __str__(self):
        return f'{self.user.username} Profile'


    def save(self, *args, **kwargs):
        previous_picture_name = None
        previous_icon_name = None
        if self.pk:
            try:
                existing_profile = Profile.objects.only('profile_picture', 'profile_icon').get(pk=self.pk)
                previous_picture_name = existing_profile.profile_picture.name
                previous_icon_name = existing_profile.profile_icon.name
            except Profile.DoesNotExist:
                previous_picture_name = None
                previous_icon_name = None

        super().save(*args, **kwargs)

        picture_changed = previous_picture_name != self.profile_picture.name
        icon_missing = not self.profile_icon
        icon_stale = previous_icon_name and previous_icon_name != self.profile_icon.name

        if picture_changed or icon_missing or icon_stale:
            self.ensure_profile_icon(force=picture_changed)

    def has_custom_profile_picture(self):
        picture_name = Path(self.profile_picture.name or '').name
        return bool(picture_name and picture_name != 'default.jpg')

    def _build_profile_icon_content(self):
        if not self.has_custom_profile_picture():
            return None

        try:
            with Image.open(self.profile_picture) as source_image:
                source_image = ImageOps.exif_transpose(source_image).convert('RGBA')
                resample_filter = getattr(Image, 'Resampling', Image).LANCZOS
                fitted_image = ImageOps.fit(source_image, PROFILE_ICON_SIZE, method=resample_filter)

                mask = Image.new('L', PROFILE_ICON_SIZE, 0)
                ImageDraw.Draw(mask).ellipse((0, 0, PROFILE_ICON_SIZE[0] - 1, PROFILE_ICON_SIZE[1] - 1), fill=255)

                output_image = Image.new('RGBA', PROFILE_ICON_SIZE, (0, 0, 0, 0))
                output_image.paste(fitted_image, (0, 0), mask)

                output_buffer = BytesIO()
                output_image.save(output_buffer, format='PNG')
                return output_buffer.getvalue()
        except Exception:
            return None

    def ensure_profile_icon(self, force=False):
        if not self.pk:
            return False

        if not self.has_custom_profile_picture():
            if self.profile_icon:
                self.profile_icon.delete(save=False)
                self.profile_icon = ''
                super().save(update_fields=['profile_icon'])
            return False

        if self.profile_icon and not force:
            return False

        icon_content = self._build_profile_icon_content()
        if not icon_content:
            return False

        icon_filename = f"{Path(self.profile_picture.name).stem}_icon.png"
        if self.profile_icon and self.profile_icon.name and Path(self.profile_icon.name).name != icon_filename:
            self.profile_icon.delete(save=False)

        self.profile_icon.save(icon_filename, ContentFile(icon_content), save=False)
        super().save(update_fields=['profile_icon'])
        return True

class GPTriviaRound(models.Model):
    creator = models.CharField(max_length=100)
    title = models.CharField(max_length=150)
    major_category = models.CharField(max_length=100)
    minor_category1 = models.CharField(max_length=100)
    minor_category2 = models.CharField(max_length=100)
    date = models.DateField()
    # The round number is an integer
    round_number = models.IntegerField()
    # The max score is float
    max_score = models.FloatField(null=True)
    # The remainder can be floats
    score_alex = models.FloatField(null=True)
    score_ichigo = models.FloatField(null=True)
    score_megan = models.FloatField(null=True)
    score_zach = models.FloatField(null=True)
    score_jenny = models.FloatField(null=True)
    score_debi = models.FloatField(null=True)
    score_dan = models.FloatField(null=True)
    score_chris = models.FloatField(null=True)
    score_drew = models.FloatField(null=True)
    score_jeff = models.FloatField(null=True)
    score_dillon = models.FloatField(null=True)
    score_paige = models.FloatField(null=True)
    score_tom = models.FloatField(null=True)
    extra_scores = jsonfield.JSONField(default=dict, blank=True)
    replay = models.BooleanField(default=False)
    cooperative = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    link = models.CharField(max_length=255, blank=True, default='https://docs.google.com/presentation/d/1gC9DR9TmQK_9ls8Npw8Sc99qKI6YN9nRqLuVj0W07ns/embed?start=false&slide=id.g717c8ec4cb_2_0')

    def __str__(self):
        return self.title


class MergedPresentation(models.Model):
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_READY, 'Ready'),
        (STATUS_FAILED, 'Failed'),
    ]

    name = models.CharField(max_length=255)
    presentation_id = models.CharField(max_length=255)
    round_names = jsonfield.JSONField(default=list)
    creator_list = jsonfield.JSONField(default=list)
    joker_round_indices = jsonfield.JSONField(null=True, blank=True)
    player_list = jsonfield.JSONField(null=True, blank=True)
    host = models.CharField(max_length=100, default='Alex')
    scorekeeper = models.CharField(max_length=100, default='Alex')
    style_points = jsonfield.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True)
    tiebreak_winner = models.CharField(max_length=100, blank=True)
    crowned_winner = models.CharField(max_length=100, blank=True, default='')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_READY)
    error_message = models.TextField(blank=True, default='')


    def __str__(self):
        return self.name


class PresentationBuildState(models.Model):
    key = models.CharField(max_length=32, unique=True, default='home_page')
    is_active = models.BooleanField(default=False)
    action = models.CharField(max_length=16, blank=True, default='')
    presentation_name = models.CharField(max_length=255, blank=True, default='')
    presentation_id = models.CharField(max_length=255, blank=True, default='')
    started_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key}: {'active' if self.is_active else 'idle'}"


class PushSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    endpoint = models.URLField(unique=True)
    p256dh = models.TextField()
    auth = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Subscription for {self.user or 'anonymous'}"


class JeopardyRound(models.Model):
    JEOPARDY = 'JEOPARDY'
    DOUBLE_JEOPARDY = 'DOUBLE_JEOPARDY'
    FINAL_JEOPARDY = 'FINAL_JEOPARDY'
    ROUND_TYPES = [
        (JEOPARDY, 'Jeopardy'),
        (DOUBLE_JEOPARDY, 'Double Jeopardy'),
        (FINAL_JEOPARDY, 'Final Jeopardy'),
    ]
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=ROUND_TYPES, default=JEOPARDY)


class JeopardyQuestion(models.Model):
    round = models.ForeignKey(JeopardyRound, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    is_active = models.BooleanField(default=True)  # Track if the question is still active
    daily_double = models.BooleanField(default=False)  # New field
