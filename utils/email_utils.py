def get_headers_value(headers, header_name):
    """Utility function to get a specific header from a list of headers."""

    for header in headers:
        if header['name'].lower() == header_name.lower():
            return header['value']
    return None