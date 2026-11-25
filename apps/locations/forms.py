from django import forms
from .models import Location, LocationImage


class LocationImageForm(forms.ModelForm):
    class Meta:
        model = LocationImage
        fields = ['image', 'caption']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'caption': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional caption'
            })
        }


class LocationForm(forms.ModelForm):
    parent = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        empty_label="-- Root Level (New House) --",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Parent Location'
    )
    
    class Meta:
        model = Location
        fields = ['name', 'location_type', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter location name'
            }),
            'location_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional description'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get all locations for parent choices
        available_locations = Location.objects.all()
        
        # If editing an existing location, exclude only the location itself to prevent self-parenting
        if self.instance and self.instance.pk:
            available_locations = available_locations.exclude(pk=self.instance.pk)
        
        # Set the queryset for the parent field
        self.fields['parent'].queryset = available_locations
        
        # If editing and instance has a parent, pre-select it
        if self.instance and self.instance.pk:
            current_parent = self.instance.get_parent()
            if current_parent:
                self.fields['parent'].initial = current_parent.pk