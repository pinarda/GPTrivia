from .models import Profile
from .profile_media import get_profile_avatar_url


def site_profile_context(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {
            "site_profile_theme": "default",
            "site_profile_icon_url": "",
            "site_profile_link": "",
        }

    profile = getattr(request.user, "profile", None)
    if profile is None:
        profile = Profile.objects.filter(user=request.user).first()

    theme = getattr(profile, "site_theme", "default") or "default"
    profile_link = f"/player_profile/{request.user.username}/"

    icon_url = get_profile_avatar_url(profile, include_default=True)

    return {
        "site_profile_theme": theme,
        "site_profile_icon_url": icon_url,
        "site_profile_link": profile_link,
    }
