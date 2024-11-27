# admin.py
from django.contrib import admin
from .models import JeopardyQuestion, JeopardyRound

@admin.action(description='Activate selected questions')
def activate_questions(modeladmin, request, queryset):
    queryset.update(is_active=True)

@admin.action(description='Deactivate selected questions')
def deactivate_questions(modeladmin, request, queryset):
    queryset.update(is_active=False)

@admin.register(JeopardyQuestion)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'round', 'is_active')  # Display columns in the list view
    list_filter = ('round', 'is_active')  # Filters for easy navigation
    search_fields = ('text',)  # Add a search box for question text
    actions = [activate_questions, deactivate_questions]  # Add actions to the admin panel

@admin.register(JeopardyRound)
class RoundAdmin(admin.ModelAdmin):
    list_display = ('title',)
