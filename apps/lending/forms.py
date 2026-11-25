from django import forms
from django.contrib.auth import get_user_model
from .models import Lending

User = get_user_model()


class LendingForm(forms.ModelForm):
    borrower_name = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter name (e.g., John Smith)',
            'list': 'frequent-borrowers',
            'autocomplete': 'off'
        }),
        help_text='Name of the person borrowing the item'
    )
    
    class Meta:
        model = Lending
        fields = ['quantity', 'borrower_name', 'borrowed_by_user', 'due_date', 'notes']
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'value': '1'
            }),
            'borrowed_by_user': forms.Select(attrs={
                'class': 'form-select'
            }),
            'due_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional notes'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make borrowed_by_user optional
        self.fields['borrowed_by_user'].required = False
        self.fields['borrowed_by_user'].empty_label = "-- Not a registered user --"
        self.fields['borrowed_by_user'].queryset = User.objects.filter(is_active=True)
        
        # If editing and borrower_name is empty but borrowed_by_user exists, populate it
        if self.instance and self.instance.pk:
            if not self.instance.borrower_name and self.instance.borrowed_by_user:
                self.fields['borrower_name'].initial = self.instance.borrowed_by_user.username