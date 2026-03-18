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
        fields = [
            'profile_picture',
            'profile_color',
            'profile_page_chrome_color',
            'profile_page_trivia_color_one',
            'profile_page_trivia_color_two',
            'profile_page_trivia_color_three',
            'profile_page_theme',
            'site_theme',
        ]
        widgets = {
            'profile_picture': forms.FileInput(),
            'profile_color': forms.TextInput(attrs={'type': 'color'}),
            'profile_page_chrome_color': forms.TextInput(attrs={'type': 'color'}),
            'profile_page_trivia_color_one': forms.TextInput(attrs={'type': 'color'}),
            'profile_page_trivia_color_two': forms.TextInput(attrs={'type': 'color'}),
            'profile_page_trivia_color_three': forms.TextInput(attrs={'type': 'color'}),
            'profile_page_theme': forms.Select(),
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
        self.fields['profile_color'].label = 'Player Color'
        self.fields['profile_page_chrome_color'].required = False
        self.fields['profile_page_chrome_color'].widget.attrs.update({
            'id': 'profile-page-chrome-input',
        })
        self.fields['profile_page_trivia_color_one'].required = False
        self.fields['profile_page_trivia_color_one'].widget.attrs.update({
            'id': 'profile-trivia-color-one-input',
        })
        self.fields['profile_page_trivia_color_two'].required = False
        self.fields['profile_page_trivia_color_two'].widget.attrs.update({
            'id': 'profile-trivia-color-two-input',
        })
        self.fields['profile_page_trivia_color_three'].required = False
        self.fields['profile_page_trivia_color_three'].widget.attrs.update({
            'id': 'profile-trivia-color-three-input',
        })
        self.fields['profile_page_theme'].required = False
        self.fields['profile_page_theme'].choices = [
            (Profile.THEME_DEFAULT, 'Dark (default)'),
            (Profile.THEME_LIGHT, 'Light'),
        ]
        self.fields['profile_page_theme'].widget.attrs.update({
            'id': 'profile-page-theme-input',
        })
        self.fields['site_theme'].required = False
        self.fields['site_theme'].choices = [
            (Profile.THEME_DEFAULT, 'Dark (default)'),
            (Profile.THEME_LIGHT, 'Light'),
        ]
        self.fields['site_theme'].widget.attrs.update({
            'id': 'profile-theme-input',
        })
        if not self.initial.get('profile_color'):
            self.initial['profile_color'] = effective_color or '#333333'
        if not self.initial.get('profile_page_chrome_color'):
            self.initial['profile_page_chrome_color'] = profile.profile_page_chrome_color or Profile.PROFILE_PAGE_CHROME_DEFAULT
        if not self.initial.get('profile_page_trivia_color_one'):
            self.initial['profile_page_trivia_color_one'] = (
                profile.profile_page_trivia_color_one or Profile.PROFILE_PAGE_TRIVIA_COLOR_ONE_DEFAULT
            )
        if not self.initial.get('profile_page_trivia_color_two'):
            self.initial['profile_page_trivia_color_two'] = (
                profile.profile_page_trivia_color_two or Profile.PROFILE_PAGE_TRIVIA_COLOR_TWO_DEFAULT
            )
        if not self.initial.get('profile_page_trivia_color_three'):
            self.initial['profile_page_trivia_color_three'] = (
                profile.profile_page_trivia_color_three or Profile.PROFILE_PAGE_TRIVIA_COLOR_THREE_DEFAULT
            )
        if not self.initial.get('profile_page_theme'):
            self.initial['profile_page_theme'] = profile.profile_page_theme or Profile.THEME_DEFAULT

    def _clean_hex_color(self, field_name):
        color = (self.cleaned_data.get(field_name) or '').strip()
        if not color:
            return ''
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise forms.ValidationError('Enter a valid hex color.')
        return color.lower()

    def clean_profile_color(self):
        return self._clean_hex_color('profile_color')

    def clean_profile_page_chrome_color(self):
        return self._clean_hex_color('profile_page_chrome_color')

    def clean_profile_page_trivia_color_one(self):
        return self._clean_hex_color('profile_page_trivia_color_one')

    def clean_profile_page_trivia_color_two(self):
        return self._clean_hex_color('profile_page_trivia_color_two')

    def clean_profile_page_trivia_color_three(self):
        return self._clean_hex_color('profile_page_trivia_color_three')

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
        if 'profile_page_chrome_color' in self.changed_data:
            profile.profile_page_chrome_color = self.cleaned_data.get('profile_page_chrome_color', '') or ''
        if 'profile_page_trivia_color_one' in self.changed_data:
            profile.profile_page_trivia_color_one = self.cleaned_data.get('profile_page_trivia_color_one', '') or ''
        if 'profile_page_trivia_color_two' in self.changed_data:
            profile.profile_page_trivia_color_two = self.cleaned_data.get('profile_page_trivia_color_two', '') or ''
        if 'profile_page_trivia_color_three' in self.changed_data:
            profile.profile_page_trivia_color_three = self.cleaned_data.get('profile_page_trivia_color_three', '') or ''
        if 'profile_page_theme' in self.changed_data:
            profile.profile_page_theme = self.cleaned_data.get('profile_page_theme', '') or Profile.THEME_DEFAULT

        if commit:
            profile.save()
        return profile


class ProfileIntroForm(forms.Form):
    profile_intro = forms.CharField(
        required=False,
        max_length=280,
        widget=forms.Textarea(
            attrs={
                'rows': 3,
                'id': 'profile-intro-input',
                'placeholder': 'Add a short intro, fun fact, or running bit for your profile.',
                'maxlength': 280,
            }
        ),
    )
