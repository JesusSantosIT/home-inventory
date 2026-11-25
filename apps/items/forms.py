import os

from django import forms
from django.conf import settings
from .models import Item, Category, ItemImage
from apps.locations.models import Location


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'parent', 'description', 'color']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Category name'
            }),
            'parent': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional description'
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically populate parent choices with hierarchical structure
        parent_choices = [('', '---------')]
        for category in Category.objects.all():
            parent_choices.append((category.pk, category.get_full_path()))
        self.fields['parent'].choices = parent_choices
        
        # Prevent circular references - exclude self and descendants when editing
        if self.instance and self.instance.pk:
            category_ids = [self.instance.pk] + [child.pk for child in self.instance.get_descendants()]
            available_parents = Category.objects.exclude(pk__in=category_ids)
            parent_choices = [('', '---------')]
            for category in available_parents:
                parent_choices.append((category.pk, category.get_full_path()))
            self.fields['parent'].choices = parent_choices


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            'name', 'description', 'quantity', 'min_quantity', 'available_for_lending', 'location', 'categories',
            'serial_number', 'brand', 'model', 'barcode', 'qr_code',
            'purchase_date', 'purchase_price', 'current_value', 'condition'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter item name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional description'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'value': '1'
            }),
            'min_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'value': '1',
                'placeholder': 'Alert threshold'
            }),
            'available_for_lending': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'location': forms.Select(attrs={
                'class': 'form-select'
            }),
            'categories': forms.CheckboxSelectMultiple(),
            'serial_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional serial number'
            }),
            'brand': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional brand'
            }),
            'model': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional model'
            }),
            'barcode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Auto-generated if left blank'
            }),
            'qr_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Auto-generated if left blank'
            }),
            'purchase_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'purchase_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'current_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'condition': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to categories checkboxes
        self.fields['categories'].widget.attrs.update({'class': 'form-check-input'})
        
        # Dynamically populate location choices with hierarchical structure
        location_choices = [('', '---------')]
        for location in Location.get_tree():
            depth = location.get_depth()
            indent = '──' * (depth - 1) if depth > 1 else ''
            location_choices.append(
                (location.pk, f"{indent} {location.name}")
            )
        self.fields['location'].choices = location_choices
        
        # Ensure categories field is properly initialized
        if not self.fields['categories'].queryset.exists():
            # Create default categories if none exist
            default_categories = ['Electronics', 'Furniture', 'Clothing', 'Tools', 'Kitchen', 'Office', 'Other']
            for cat_name in default_categories:
                Category.objects.get_or_create(name=cat_name)
        
        # Refresh the queryset
        self.fields['categories'].queryset = Category.objects.all()


class ItemImageForm(forms.ModelForm):
    class Meta:
        model = ItemImage
        fields = ['image', 'caption', 'is_primary']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'caption': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional caption'
            }),
            'is_primary': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            ext = os.path.splitext(image.name)[1].lower()
            if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
                raise forms.ValidationError(
                    f'File type "{ext}" is not allowed. Allowed types: '
                    f'{", ".join(settings.ALLOWED_IMAGE_EXTENSIONS)}'
                )
        return image