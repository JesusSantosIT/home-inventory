"""Outbound API client - call a remote household instance's API using the
remote_api_key they shared with us."""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # seconds


class RemoteAPIError(Exception):
    """Raised when a remote household API call fails."""
    pass


def _api_url(household, path):
    return household.base_url.rstrip('/') + '/users/api/v1/' + path.lstrip('/')


def _get(household, path):
    """GET a remote API endpoint, returning parsed JSON."""
    if not household.remote_api_key:
        raise RemoteAPIError('No API key stored for this household')
    try:
        resp = requests.get(
            _api_url(household, path),
            headers={'X-API-Key': household.remote_api_key},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        logger.warning('Remote API request to %s failed: %s', household.base_url, e)
        raise RemoteAPIError(f'Could not reach {household.name}: {e}')

    if resp.status_code == 401:
        raise RemoteAPIError('Remote household rejected the API key (401)')
    if resp.status_code == 403:
        raise RemoteAPIError('Remote household denied access (403)')
    if resp.status_code != 200:
        raise RemoteAPIError(f'Remote household returned HTTP {resp.status_code}')
    try:
        return resp.json()
    except ValueError:
        raise RemoteAPIError('Remote household returned invalid JSON')


def fetch_available_items(household):
    """Fetch items the remote household has available for lending."""
    return _get(household, 'available-items/')


def fetch_item_detail(household, item_id):
    """Fetch details of a specific item from the remote household."""
    return _get(household, f'items/{item_id}/')


def _post(household, path, payload):
    """POST JSON to a remote API endpoint, returning parsed JSON."""
    if not household.remote_api_key:
        raise RemoteAPIError('No API key stored for this household')
    try:
        resp = requests.post(
            _api_url(household, path),
            json=payload,
            headers={'X-API-Key': household.remote_api_key},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        logger.warning('Remote API request to %s failed: %s', household.base_url, e)
        raise RemoteAPIError(f'Could not reach {household.name}: {e}')

    try:
        data = resp.json()
    except ValueError:
        data = {}

    if resp.status_code == 401:
        raise RemoteAPIError('Remote household rejected the API key (401)')
    if resp.status_code == 403:
        raise RemoteAPIError('Remote household denied access (403)')
    if resp.status_code != 200:
        detail = data.get('error') or data.get('message') or f'HTTP {resp.status_code}'
        raise RemoteAPIError(f'Remote household error: {detail}')
    return data


def request_lending(household, item_id, quantity, borrower_name, due_date=None):
    """Request to borrow an item from the remote household."""
    payload = {
        'item_id': item_id,
        'quantity': quantity,
        'borrower_name': borrower_name,
    }
    if due_date:
        # Remote expects ISO 8601; append time if only a date was given
        payload['due_date'] = due_date if 'T' in due_date else due_date + 'T00:00:00'
    return _post(household, 'request-lending/', payload)
