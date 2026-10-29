from decimal import Decimal

from django import forms
from django.utils import timezone

from .schema import QUESTIONS, SECTIONS, is_applicable


class QuestionnaireForm(forms.Form):
    def __init__(self, *args, complete=False, **kwargs):
        self.complete = complete
        super().__init__(*args, **kwargs)
        for q in QUESTIONS:
            options = {"label": q["label"], "required": False}
            kind = q["kind"]
            if kind in {"choice", "multi"}:
                choices = [(v, v) for v in q["choices"]]
                if kind == "multi":
                    field = forms.MultipleChoiceField(
                        choices=choices, widget=forms.CheckboxSelectMultiple, **options
                    )
                else:
                    field = forms.ChoiceField(choices=[("", "Choisir…")] + choices, **options)
            elif kind == "boolean":
                field = forms.BooleanField(**options)
            elif kind in {"integer", "year"}:
                field = forms.IntegerField(
                    min_value=1900 if kind == "year" else 0,
                    max_value=timezone.now().year if kind == "year" else 1000000,
                    **options,
                )
            elif kind == "money":
                field = forms.DecimalField(min_value=0, max_digits=20, decimal_places=0, **options)
            elif kind == "email":
                field = forms.EmailField(max_length=254, **options)
            else:
                field = forms.CharField(
                    max_length=5000 if kind == "long" else 255,
                    widget=forms.Textarea(attrs={"rows": 3}) if kind == "long" else forms.TextInput,
                    **options,
                )
            field.widget.attrs["class"] = "fa-input"
            field.widget.attrs["data-question"] = q["key"]
            field.widget.attrs["data-required-final"] = "1" if q["required"] else "0"
            if q["condition"]:
                field.widget.attrs["data-condition-field"] = q["condition"][0]
                field.widget.attrs["data-condition-value"] = q["condition"][1]
            self.fields[q["key"]] = field

    @property
    def sections(self):
        return [
            {"title": section["title"], "fields": [self[q["key"]] for q in section["questions"]]}
            for section in SECTIONS
        ]

    def clean(self):
        cleaned = super().clean()
        for q in QUESTIONS:
            key = q["key"]
            if not is_applicable(q, cleaned):
                cleaned[key] = [] if q["kind"] == "multi" else ""
                self._errors.pop(key, None)
                continue
            value = cleaned.get(key)
            empty = (
                value is None
                or value == ""
                or value == []
                or (q["kind"] == "boolean" and value is False)
            )
            if self.complete and q["required"] and empty:
                self.add_error(key, "Cette réponse est nécessaire pour finaliser le questionnaire.")
        if self.complete and not cleaned.get("q11_none"):
            for key in ("q11_permanent", "q11_temporary"):
                if cleaned.get(key) is None:
                    self.add_error(
                        key, "Indiquez l’effectif, y compris 0, ou cochez Aucun salarié."
                    )
        if cleaned.get("q11_none"):
            cleaned["q11_permanent"] = cleaned["q11_temporary"] = 0
        if self.complete and "Autre" in (cleaned.get("q27_support_received") or []) + (
            cleaned.get("q27_support_desired") or []
        ):
            if not cleaned.get("q27_other"):
                self.add_error("q27_other", "Précisez l’autre accompagnement.")
        return cleaned

    def answers(self):
        return {
            key: str(value) if isinstance(value, Decimal) else value
            for key, value in self.cleaned_data.items()
            if value is not None
        }
