from django import forms
from .models import Warranty


class WarrantyForm(forms.ModelForm):
    class Meta:
        model = Warranty
        fields = ['provider', 'policy_number', 'purchase_date', 'expiration_date', 
                 'coverage_details', 'notes']
        widgets = {
            'provider': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Warranty provider (e.g., Sony, Best Buy)'
            }),
            'policy_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional policy number'
            }),
            'purchase_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'expiration_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'coverage_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'What does the warranty cover?'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes'
            }),
        }