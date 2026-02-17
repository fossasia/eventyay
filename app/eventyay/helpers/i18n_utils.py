from django.utils.translation import get_language_info

def get_styled_language_name(code, natural_name):
    """
    Returns the language name in the format "Translated Name (Native Name)".
    Example: "German (Deutsch)"
    """
    try:
        lang_info = get_language_info(code)
        translated_name = lang_info['name_translated']
    except KeyError:
        translated_name = natural_name

    # Check if translated name and natural name are the same (case-insensitive)
    if translated_name.lower() == natural_name.lower():
        return translated_name
    
    return f"{translated_name} ({natural_name})"

def get_sorted_grouped_locales(current_locale=None):
    """
    Returns a sorted and grouped list of locales for UI rendering.
    
    Structure:
    [
        {
            'code': 'de',
            'name': 'German (Deutsch)',
            'natural_name': 'Deutsch',
            'is_variant': False,
            'variants': [
                {'code': 'de-formal', 'name': 'Formal', 'natural_name': 'Formal', ...},
                {'code': 'de-informal', 'name': 'Informal', 'natural_name': 'Informal', ...}
            ]
        },
        ...
    ]
    """
    from django.conf import settings # Import here to avoid circular dependency if any
    
    languages_config = getattr(settings, '_LANGUAGES_CONFIG', {})
    if not languages_config:
        # Fallback to settings.LANGUAGES if config is missing
        # Construct a minimal config from LANGUAGES tuple
        languages_config = {
            code: {'name': name, 'natural_name': name} 
            for code, name in getattr(settings, 'LANGUAGES', [])
        }
    
    
    # helper to check if a code is a variant
    # Variants are defined in settings via the optional 'variant_of' key in each language config entry.
    # A locale with a non-empty 'variant_of' value is treated as a variant of the referenced parent locale.
    
    grouped = {}
    
    # First pass: Identify base languages and variants
    for code, info in languages_config.items():
        # In production environments, incubating languages are not exposed in the UI.
        is_incubating = info.get('incubating', False)
        if is_incubating and getattr(settings, 'IS_PRODUCTION', False):
             continue
             
        variant_of = info.get('variant_of')
        
        try:
            name_translated = get_language_info(code)['name_translated']
        except KeyError:
            # Fallback if django doesn't know this code
            name_translated = str(info.get('name', info.get('natural_name', code)))

        entry = {
            'code': code,
            'name_translated': name_translated,
            'natural_name': info['natural_name'],
            'styled_name': get_styled_language_name(code, info['natural_name']),
            'variants': []
        }
        
        if variant_of:
            # It's a variant
            if variant_of not in grouped:
                # Parent not found (e.g. filtered out because incubating)
                # Treat as standalone entry
                grouped[code] = entry
                continue
            # We will handle variants after collecting all objects in the second pass
            # We skip adding it to 'grouped' here to avoid duplication if parent exists
        else:
            grouped[code] = entry

    # Second pass: Associate variants with their base languages
    for code, info in languages_config.items():
        is_incubating = info.get('incubating', False)
        if is_incubating and getattr(settings, 'IS_PRODUCTION', False):
             continue

        variant_of = info.get('variant_of')
        if variant_of and variant_of in grouped:
             # Let's check settings for 'variant_label' or parse 'name'
             variant_label = info.get('variant_label', info['name'])
             
             variant_entry = {
                 'code': code,
                 'name': variant_label, 
                 'styled_name': variant_label, # Variants usually just show the variant name
                 'label': variant_label, # Compatibility
             }
             grouped[variant_of]['variants'].append(variant_entry)
        
        # Ensure base entries have 'label' for compatibility
        if code in grouped:
             grouped[code]['label'] = grouped[code]['styled_name']

    # Convert to list and sort
    result_list = list(grouped.values())
    
    # Sort by translated name in CURRENT locale
    # Note: We use simple case-insensitive sorting here as a lightweight "locale-aware" sort.
    # Full ICU collation would require PyICU or relying on system locale, which is not guaranteed.
    def sort_key(item):
        return item['name_translated'].lower()
        
    result_list.sort(key=sort_key)
    
    # Pin current locale to the top
    if current_locale:
        # Look for an exact code match in result_list and move that item to the front.
        # The 'code' in result_list matches keys in _LANGUAGES_CONFIG (e.g. 'en', 'de', 'zh-hans')
        pinned_item = None
        for i, item in enumerate(result_list):
            if item['code'] == current_locale:
                pinned_item = result_list.pop(i)
                break
        
        if pinned_item:
            result_list.insert(0, pinned_item)
            
    return result_list
