"""Text-first source delivery without repeating the same bytes as base64."""


def excerpt_view(excerpt, query):
    representation = query.get('format', 'text')
    if representation not in ('text', 'base64', 'full'):
        raise ValueError('excerpt format must be text|base64|full')
    if representation == 'full':
        return excerpt
    omitted = 'data_base64' if representation == 'text' else 'text'
    result = {key: value for key, value in excerpt.items() if key != omitted}
    result['next_offset'] = excerpt['offset'] + excerpt['bytes_read'] if excerpt.get('truncated') else None
    result['content_format'] = representation
    if representation == 'text' and 'data_base64' in excerpt:
        result['exact_bytes'] = 'request format=base64 at the same offset/max_bytes for original bytes'
    return result
