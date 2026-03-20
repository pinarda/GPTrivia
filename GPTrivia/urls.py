"""GPTrivia URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, reverse_lazy
from . import views
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import (
    LoginView, LogoutView,
    PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView,
    PasswordChangeView, PasswordChangeDoneView,
)
from django.conf import settings
from django.conf.urls.static import static
from django.forms.models import model_to_dict
from django.views.decorators.csrf import csrf_exempt
try:
    from debug_toolbar.toolbar import debug_toolbar_urls
except ImportError:
    def debug_toolbar_urls():
        return []
from django.views.generic import TemplateView



urlpatterns = [
    path('', views.home, name='home'),
    path('blog/', views.blog_index, name='blog_index'),
    path('blog/joker-stats/', views.blog_joker_stats, name='blog_joker_stats'),
    path('blog/other-trivia-plots/', views.blog_other_trivia_plots, name='blog_other_trivia_plots'),
    path('blog/roboalex-1-0/', views.blog_roboalex, name='blog_roboalex'),
    path('rounds/', views.rounds_list, name='rounds_list'),
    path('player_analysis/', views.player_analysis, name='player_analysis'),
    path('player_analysis_legacy/', views.player_analysis_legacy, name='player_analysis_legacy'),
    path('player_profile/<str:player_name>/', views.player_profile, name='player_profile'),
    path('player_profile/<str:player_name>/stats/', views.player_profile_stats, name='player_profile_stats'),
    path('player_profile/<str:player_name>/creator-panels/', views.player_profile_creator_panels, name='player_profile_creator_panels'),
    path('player_profile/<str:player_name>/intro/', views.update_profile_intro, name='update_profile_intro'),
    path('player_media/picture/<str:player_name>/<str:version>/', views.profile_picture_media, name='profile_picture_media'),
    path('player_media/avatar/<str:player_name>/<str:version>/', views.profile_avatar_media, name='profile_avatar_media'),
    path('player_profile_round/<int:round_id>/category/', views.update_profile_round_category, name='update_profile_round_category'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('accounts/password_change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('accounts/password_changed/', views.CustomPasswordChangeDoneView.as_view(), name='password_changed'),
    path('admin/', admin.site.urls),
    path('api/v1/scoresheet-bootstrap/', views.scoresheet_bootstrap, name='scoresheet_bootstrap'),
    path('api/v1/scoresheet-presentation-meta/', views.scoresheet_presentation_meta, name='scoresheet_presentation_meta'),
    path('api/v1/trivia-rounds/', views.TriviaRoundList.as_view(), name='trivia_rounds_list'),
    path('api/v1/presentations/', views.PresentationList.as_view(), name='presentations'),
    path('api-token-auth/', csrf_exempt(views.CustomObtainAuthToken.as_view()), name='api_token_auth'),
    path('api/v1/player-profile/<str:player_name>/', views.PlayerProfileAPI.as_view(), name='player_profile_api'),
    path('scoresheet/', views.scoresheet, name='scoresheet'),
    path('scoresheet_new/', views.scoresheet_new, name='scoresheet_new'),
    path('save_scores/', csrf_exempt(views.save_scores), name='save_scores'),
    path('create_round/<str:date>/<int:number>/', csrf_exempt(views.create_round), name='create_round'),
    path('delete_round/<int:round_id>/', csrf_exempt(views.delete_round), name='delete_round'),
    path('round_maker/', views.RoundMaker.as_view(), name='round_maker'),
    path('icon_view/', views.IconView.as_view(), name='icon_view'),
    path('autogen/', views.AutoGenView.as_view(), name='autogen'),
    path('generate_idea/', views.GenerateIdeaView.as_view(), name='generate_round'),
    path('preview/', views.PreviewView.as_view(), name='preview'),
    path('share/', views.ShareView.as_view(), name='share'),
    path('upload_profile_picture/', views.upload_profile_picture, name='upload_profile_picture'),
    # path('compute-pca/', views.compute_pca, name='compute_pca'),
    # path('compute-correlation-matrix/', views.compute_correlation_matrix, name='compute_correlation_matrix'),
    # path('compute-3d-surface-data/', views.compute_3d_surface_data, name='compute_3d_surface_data'),
    path('player_analysis_plot/', views.player_analysis_plot, name='player_analysis_plot'),
    path('button/', views.buzzer_page, name='button_page'),
    # path('profilepic/', views.profilepic, name='profilepic'),
    path('api/question/<int:question_id>/', views.get_j_question, name='get_j_question'),
    path('api/question/<int:question_id>/deactivate/', views.deactivate_j_question, name='deactivate_j_question'),
    path('jeopardy/', views.jeopardy_screen, name='jeopardy_screen'),
    path('double-jeopardy/', views.double_jeopardy_screen, name='double_jeopardy_screen'),
    path('final-jeopardy/', views.final_jeopardy_screen, name='final_jeopardy_screen'),
    path('api/save-rounds/', views.save_rounds, name='save_rounds'),
    path("api/collect_rounds/", views.collect_rounds_api, name="collect_rounds_api"),
    path("api/save-available-round-metadata/", views.save_available_round_metadata, name="save_available_round_metadata"),
    path('api/save-subscription/', views.save_subscription, name='save_subscription'),
    path('sw.js', TemplateView.as_view(template_name="sw.js", content_type='application/javascript')),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + debug_toolbar_urls()
