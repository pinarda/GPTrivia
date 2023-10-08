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
from .views import CustomPasswordChangeDoneView
from django.conf import settings
from django.conf.urls.static import static
from .views import CustomObtainAuthToken
from django.forms.models import model_to_dict
from django.views.decorators.csrf import csrf_exempt
from .views import RoundMaker, GenerateIdeaView, PreviewView, ShareView



urlpatterns = [
    path('', views.home, name='home'),
    path('rounds/', views.rounds_list, name='rounds_list'),
    path('player_analysis/', views.player_analysis, name='player_analysis'),
    path('player_analysis_legacy/', views.player_analysis_legacy, name='player_analysis_legacy'),
    path('player_profile/<str:player_name>/', views.player_profile, name='player_profile'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('accounts/password_change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('accounts/password_changed/', views.CustomPasswordChangeDoneView.as_view(), name='password_changed'),
    path('admin/', admin.site.urls),
    path('api/v1/trivia-rounds/', views.TriviaRoundList.as_view(), name='trivia_rounds_list'),
    path('api/v1/presentations/', views.PresentationList.as_view(), name='presentations'),
    path('api-token-auth/', csrf_exempt(CustomObtainAuthToken.as_view()), name='api_token_auth'),
    path('api/v1/player-profile/<str:player_name>/', views.PlayerProfileAPI.as_view(), name='player_profile_api'),
    path('scoresheet/', views.scoresheet, name='scoresheet'),
    path('scoresheet_new/', views.scoresheet_new, name='scoresheet_new'),
    path('save_scores/', csrf_exempt(views.save_scores), name='save_scores'),
    path('create_round/<str:date>/<int:number>/', csrf_exempt(views.create_round), name='create_round'),
    path('delete_round/<int:round_id>/', csrf_exempt(views.delete_round), name='delete_round'),
    path('round_maker/', RoundMaker.as_view(), name='round_maker'),
    path('generate_idea/', GenerateIdeaView.as_view(), name='generate_round'),
    path('preview/', PreviewView.as_view(), name='preview'),
    path('share/', ShareView.as_view(), name='share'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
