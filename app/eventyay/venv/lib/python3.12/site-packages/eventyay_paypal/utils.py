
def safe_get(data, keys, default=None):
    """
    Recursively calls .get() on a dictionary to safely access nested keys.

    Args:
        data (dict): The dictionary to access.
        keys (list): The list of keys to access, in order.
        default: The value to return if any key is missing or not a dictionary.

    Returns:
        The value at the accessed key, or the default value if any key is missing or not a dictionary.
    """
    if not keys:
        return data
    key = keys[0]
    value = data.get(key)
    if not keys[1:]:
        return value if value is not None else default
    if isinstance(value, dict):
        return safe_get(value, keys[1:], default=default)
    return default
