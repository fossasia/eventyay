from django import forms

from django_scopes.forms import (
    SafeModelChoiceField, SafeModelMultipleChoiceField,
)

from .models import Comment, CommentGroup


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("post", )
        field_classes = {
            "post": SafeModelChoiceField,
        }


class CommentGroupForm(forms.ModelForm):
    class Meta:
        model = CommentGroup
        fields = ("comments", )
        field_classes = {
            "comments": SafeModelMultipleChoiceField,
        }
