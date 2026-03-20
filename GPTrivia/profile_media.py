from pathlib import Path


def build_cache_busted_media_url(file_field):
    if not file_field:
        return ''

    try:
        base_url = file_field.url
    except Exception:
        return ''

    return base_url


def get_profile_avatar_url(profile, include_default=False):
    if not profile:
        return ''

    icon_url = build_cache_busted_media_url(getattr(profile, 'profile_icon', None))
    if icon_url:
        return icon_url

    has_custom_picture = False
    if hasattr(profile, 'has_custom_profile_picture'):
        has_custom_picture = profile.has_custom_profile_picture()

    if has_custom_picture or include_default:
        return build_cache_busted_media_url(getattr(profile, 'profile_picture', None))

    return ''


def get_profile_picture_url(profile, default_url='/media/default.jpg'):
    if not profile:
        return default_url

    picture_url = build_cache_busted_media_url(getattr(profile, 'profile_picture', None))
    return picture_url or default_url
