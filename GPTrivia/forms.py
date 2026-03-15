import re
from io import BytesIO
from pathlib import Path

from django import forms
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from .models import GPTriviaRound, Profile
from .player_scores import get_player_color

class GPTriviaRoundForm(forms.ModelForm):
    class Meta:
        model = GPTriviaRound
        fields = [
            'creator', 'title', 'major_category', 'minor_category1', 'minor_category2',
            'date', 'round_number', 'max_score',
            'score_alex', 'score_ichigo', 'score_megan', 'score_zach', 'score_jenny', 'score_debi',
            'score_dan', 'score_chris', 'score_drew', 'score_tom'
        ]

class ProfilePictureForm(forms.ModelForm):
    crop_x = forms.FloatField(required=False, widget=forms.HiddenInput())
    crop_y = forms.FloatField(required=False, widget=forms.HiddenInput())
    crop_size = forms.FloatField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Profile
        fields = ['profile_picture', 'profile_color', 'site_theme']
        widgets = {
            'profile_color': forms.TextInput(attrs={'type': 'color'}),
            'site_theme': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profile = self.instance
        effective_color = ''
        if getattr(profile, 'user_id', None):
            effective_color = profile.profile_color or get_player_color(profile.user.username)

        self.fields['profile_picture'].required = False
        self.fields['profile_picture'].widget.attrs.update({
            'accept': 'image/*',
            'id': 'profile-picture-input',
        })
        self.fields['profile_color'].required = False
        self.fields['profile_color'].widget.attrs.update({
            'id': 'profile-color-input',
        })
        self.fields['site_theme'].required = False
        self.fields['site_theme'].widget.attrs.update({
            'id': 'profile-theme-input',
        })
        self.initial.setdefault('profile_color', effective_color or '#333333')

    def clean_profile_color(self):
        color = (self.cleaned_data.get('profile_color') or '').strip()
        if not color:
            return ''
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise forms.ValidationError('Enter a valid hex color.')
        return color.lower()

    def _build_cropped_profile_picture(self, uploaded_picture):
        crop_x = self.cleaned_data.get('crop_x')
        crop_y = self.cleaned_data.get('crop_y')
        crop_size = self.cleaned_data.get('crop_size')
        if crop_x is None or crop_y is None or crop_size is None or crop_size <= 0:
            return uploaded_picture

        uploaded_picture.seek(0)
        with Image.open(uploaded_picture) as source_image:
            source_image = ImageOps.exif_transpose(source_image)
            width, height = source_image.size

            size = max(1, min(int(round(crop_size)), width, height))
            left = int(round(crop_x))
            top = int(round(crop_y))

            left = max(0, min(left, width - size))
            top = max(0, min(top, height - size))
            right = left + size
            bottom = top + size

            cropped_image = source_image.crop((left, top, right, bottom))
            image_format = 'PNG' if 'A' in cropped_image.getbands() else 'JPEG'
            if image_format == 'JPEG':
                cropped_image = cropped_image.convert('RGB')

            output_buffer = BytesIO()
            cropped_image.save(output_buffer, format=image_format, quality=95)
            output_buffer.seek(0)

        suffix = '.png' if image_format == 'PNG' else '.jpg'
        filename = f"{Path(uploaded_picture.name).stem}_cropped{suffix}"
        return ContentFile(output_buffer.getvalue(), name=filename)

    def save(self, commit=True):
        profile = super().save(commit=False)
        uploaded_picture = self.cleaned_data.get('profile_picture')
        if uploaded_picture:
            profile.profile_picture = self._build_cropped_profile_picture(uploaded_picture)

        if 'profile_color' in self.changed_data:
            profile.profile_color = self.cleaned_data.get('profile_color', '') or ''

        if commit:
            profile.save()
        return profile
