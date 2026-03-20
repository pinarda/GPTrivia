from pathlib import Path
from django.urls import reverse


def build_cache_busted_media_url(file_field):
    if not file_field:
        return ''

    try:
        base_url = file_field.url
    except Exception:
        return ''

    return base_url


def _profile_media_version_token(file_field, fallback='default'):
    file_name = Path(getattr(file_field, 'name', '') or '').name
    if not file_name:
        return fallback
    return file_name.replace('.', '-')


def get_profile_avatar_url(profile, include_default=False):
    if not profile or not getattr(profile, 'user_id', None):
        return ''

    has_custom_picture = False
    if hasattr(profile, 'has_custom_profile_picture'):
        has_custom_picture = profile.has_custom_profile_picture()

    profile_icon = getattr(profile, 'profile_icon', None)
    if profile_icon:
        return reverse(
            'profile_avatar_media',
            kwargs={
                'player_name': profile.user.username,
                'version': _profile_media_version_token(profile_icon, fallback='icon'),
            },
        )

    if has_custom_picture or include_default:
        profile_picture = getattr(profile, 'profile_picture', None)
        return reverse(
            'profile_avatar_media',
            kwargs={
                'player_name': profile.user.username,
                'version': _profile_media_version_token(profile_picture, fallback='picture'),
            },
        )

    return ''


def get_profile_picture_url(profile, default_url='/media/default.jpg'):
    if not profile or not getattr(profile, 'user_id', None):
        return default_url

    profile_picture = getattr(profile, 'profile_picture', None)
    return reverse(
        'profile_picture_media',
        kwargs={
            'player_name': profile.user.username,
            'version': _profile_media_version_token(profile_picture, fallback='picture'),
        },
    )
