from django.contrib import admin
from .models import Movie, Review

# Register your models here.
class MovieAdmin(admin.ModelAdmin):
    ordering = ['name']
    search_fields = ['name']
    list_display = ['id', 'name', 'amount_left']   # show in the list view

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and obj.amount_left == 0:
            ro.append('amount_left')  # lock the field once it hits 0
        return ro

admin.site.register(Movie, MovieAdmin)
admin.site.register(Review)
