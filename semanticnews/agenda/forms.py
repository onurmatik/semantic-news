import calendar
from datetime import date

from django import forms
from django.utils import timezone

from semanticnews.agenda.localities import get_locality_form_choices

from .models import Category


class EventSuggestForm(forms.Form):
    start_date = forms.DateField()
    end_date = forms.DateField()
    locality = forms.ChoiceField(
        choices=get_locality_form_choices(),
        required=False,
        label="Locality",
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

    def clean_locality(self):
        value = self.cleaned_data.get("locality")
        return value or None


class FindMajorEventsForm(forms.Form):
    now = timezone.now()
    YEAR_CHOICES = [(y, y) for y in range(now.year - 5, now.year + 3)]
    MONTH_CHOICES = [(m, f"{m:02d}") for m in range(1, 13)]

    year = forms.ChoiceField(choices=YEAR_CHOICES, initial=now.year, label="Year")
    month = forms.ChoiceField(choices=MONTH_CHOICES, initial=now.month, label="Month")

    locality = forms.ChoiceField(
        choices=get_locality_form_choices(blank_label="(Any)"),
        required=False,
        label="Locality",
    )

    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(), required=False, label="Categories"
    )

    limit = forms.IntegerField(min_value=1, initial=1, label="Max events to create")
    min_significance = forms.IntegerField(
        min_value=1,
        max_value=5,
        initial=4,
        label="Minimum significance rating",
        help_text="Ignore suggestions rated below this value (1=very low, 5=very high)",
    )
    distance_threshold = forms.FloatField(initial=0.15, min_value=0.0, label="Semantic distance threshold")

    def clean_month(self):
        # coerce to int
        return int(self.cleaned_data["month"])

    def clean_year(self):
        return int(self.cleaned_data["year"])

    def clean_locality(self):
        value = self.cleaned_data.get("locality")
        return value or None
