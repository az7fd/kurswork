from django import forms
from .models import Movies

class MovieForm(forms.ModelForm):
    class Meta:
        model = Movies
        fields = ('title', 'year', 'description', 'imbd_rating', 'poster')