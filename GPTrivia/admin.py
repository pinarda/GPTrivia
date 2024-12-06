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
    list_display = ('text', 'round', 'is_active', 'daily_double')  # Display columns in the list view
    list_filter = ('round', 'is_active', 'daily_double')  # Filters for easy navigation
    search_fields = ('text',)  # Add a search box for question text
    actions = [activate_questions, deactivate_questions]  # Add actions to the admin panel

    # Define custom actions
    actions = ['make_daily_double', 'remove_daily_double', 'activate_questions', 'deactivate_questions']

    # Action to activate Daily Double
    def make_daily_double(self, request, queryset):
        queryset.update(daily_double=True)
        self.message_user(request, "Selected questions are now marked as Daily Double.")

    make_daily_double.short_description = "Mark selected questions as Daily Double"

    # Action to deactivate Daily Double
    def remove_daily_double(self, request, queryset):
        queryset.update(daily_double=False)
        self.message_user(request, "Selected questions are no longer marked as Daily Double.")

    remove_daily_double.short_description = "Remove Daily Double status from selected questions"

    def activate_questions(modeladmin, request, queryset):
        queryset.update(is_active=True)

    activate_questions.short_description = "Activate selected questions"

    def deactivate_questions(modeladmin, request, queryset):
        queryset.update(is_active=False)

    deactivate_questions.short_description = "Deactivate selected questions"


@admin.register(JeopardyRound)
class RoundAdmin(admin.ModelAdmin):
    list_display = ('title',)
