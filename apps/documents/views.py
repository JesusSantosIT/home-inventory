from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse
from .models import Document
from .forms import DocumentForm
from apps.users.decorators import editor_required
from django.core.paginator import Paginator


@login_required
def document_list(request):
    """Display all documents (paginated)"""
    documents = Document.objects.select_related('item', 'uploaded_by').all()
    paginator = Paginator(documents, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'documents/document_list.html', {'documents': page_obj})


@login_required
def document_detail(request, pk):
    """Display details of a specific document"""
    document = get_object_or_404(Document.objects.select_related('item', 'uploaded_by'), pk=pk)
    
    # Build breadcrumb navigation
    from django.urls import reverse
    breadcrumbs = [
        {'name': 'Documents', 'url': reverse('documents:document_list')},
    ]
    
    # Add item breadcrumb if document is linked to an item
    if document.item:
        breadcrumbs.append({
            'name': document.item.name,
            'url': reverse('items:item_detail', args=[document.item.pk])
        })
    
    breadcrumbs.append({'name': document.title, 'url': None})
    
    return render(request, 'documents/document_detail.html', {
        'document': document,
        'breadcrumbs': breadcrumbs,
    })


@login_required
@editor_required
def document_create(request, item_pk=None):
    """Create a new document"""
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.uploaded_by = request.user
            if item_pk:
                from apps.items.models import Item
                document.item = get_object_or_404(Item, pk=item_pk)
            document.save()
            messages.success(request, f'Document "{document.title}" uploaded successfully.')
            return redirect('document_detail', pk=document.pk)
    else:
        form = DocumentForm()
        if item_pk:
            from apps.items.models import Item
            form.fields['item'].initial = get_object_or_404(Item, pk=item_pk)
            form.fields['item'].widget.attrs['readonly'] = True
    
    return render(request, 'documents/document_form.html', {
        'form': form,
        'action': 'Upload'
    })


@login_required
@editor_required
def document_update(request, pk):
    """Update an existing document"""
    document = get_object_or_404(Document, pk=pk)
    
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, instance=document)
        if form.is_valid():
            form.save()
            messages.success(request, f'Document "{document.title}" updated successfully.')
            return redirect('document_detail', pk=document.pk)
    else:
        form = DocumentForm(instance=document)
    
    return render(request, 'documents/document_form.html', {
        'form': form,
        'document': document,
        'action': 'Update'
    })


@login_required
@editor_required
def document_delete(request, pk):
    """Delete a document"""
    document = get_object_or_404(Document, pk=pk)
    
    if request.method == 'POST':
        document_name = document.title
        document.delete()
        messages.success(request, f'Document "{document_name}" deleted successfully.')
        return redirect('document_list')
    
    return render(request, 'documents/document_confirm_delete.html', {'document': document})


@login_required
def document_download(request, pk):
    """Download a document file"""
    document = get_object_or_404(Document, pk=pk)
    return FileResponse(document.file.open('rb'), as_attachment=True, filename=document.file.name)
