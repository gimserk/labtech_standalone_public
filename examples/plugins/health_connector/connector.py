"""Harmless local-only reference connector; no course or student data."""


def handle(operation, payload):
    if operation == 'health':
        return {'healthy': True}
    if operation == 'validate_configuration':
        return {'valid': isinstance(payload, dict)}
    return {'error': 'unsupported_operation'}
