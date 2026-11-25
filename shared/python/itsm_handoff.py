"""Shared contract for ITSM request handoffs."""
from datetime import datetime


def oldest_first(requests):
    def order(row):
        value = row.get('created_at')
        if not isinstance(value, str):
            raise ValueError('Expected CREATED_AT as an ISO 8601 timestamp with offset')
        created = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if created.utcoffset() is None:
            raise ValueError('CREATED_AT must include a timezone offset')
        return created, row['request_id']

    return sorted(requests, key=order)


def validate_requests(requests, limit):
    if not isinstance(requests, list) or len(requests) > limit:
        raise ValueError("Invalid intake size")
    ids = set()
    for request in requests:
        if not isinstance(request, dict) or set(request) - {"target_system", "component", "created_at"} != {"request_id", "revision", "title", "summary"}:
            raise ValueError("Invalid intake fields")
        if not all(isinstance(value, str) and value.strip() and len(value) <= limit
                   for value, limit in zip(
                       (request[k] for k in ('request_id', 'revision', 'title', 'summary')),
                       (200, 200, 240, 16000))):
            raise ValueError('Invalid ITSM row fields')
        if request['request_id'] in ids:
            raise ValueError('Duplicate ITSM request ID in query result')
        ids.add(request['request_id'])
    return requests
