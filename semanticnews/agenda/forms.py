from datetime import date
import calendar

from django import forms

from .models import Locality, Category


class EventSuggestForm(forms.Form):
    start_date = forms.DateField()
    end_date = forms.DateField()
    locality = forms.ModelChoiceField(
        queryset=Locality.objects.all().order_by("-is_default", "name"),
        required=False,
        empty_label="Global",
    )
    categories = forms.ModelMultipleChoiceField(queryset=Category.objects.all(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            today = date.today()
            first = date(today.year, today.month, 1)
            last = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
            self.initial.setdefault('start_date', first)
            self.initial.setdefault('end_date', last)
