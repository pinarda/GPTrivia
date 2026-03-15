from .models import Profile


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

    icon_url = ""
    if profile:
        if profile.profile_icon:
            icon_url = profile.profile_icon.url
        elif profile.profile_picture:
            icon_url = profile.profile_picture.url

    return {
        "site_profile_theme": theme,
        "site_profile_icon_url": icon_url,
        "site_profile_link": profile_link,
    }
