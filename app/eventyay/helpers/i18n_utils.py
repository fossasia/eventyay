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
    # We assume variants are defined in settings with 'parent' key or implicit via naming convention if we want
    # But based on plan, we will add 'parent' or similar to _LANGUAGES_CONFIG.
    # For now, let's implement the logic assuming we have 'variant_of' in config, or we derive it.
    
    grouped = {}
    
    # First pass: Identify base languages and variants
    for code, info in languages_config.items():
        # Skip incubating if not in dev/production depending on flag? 
        # Using settings.LANGUAGES logic:
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
                 # Parent not seen yet or doesn't exist (should not happen if config is correct)
                 # Create placeholder if needed, or wait. 
                 # Better: iterate all, put into list, then process.
                 pass
             # We will handle variants after collecting all objects
        else:
            grouped[code] = entry

    # Second pass: Associate variants
    for code, info in languages_config.items():
        is_incubating = info.get('incubating', False)
        if is_incubating and getattr(settings, 'IS_PRODUCTION', False):
             continue

        variant_of = info.get('variant_of')
        if variant_of and variant_of in grouped:
             # It's a variant of an existing base
             # Use the specific name for the variant (e.g. "Formal", "Informal")
             # We might need a 'variant_label' in settings, or derive it.
             # For 'de-formal', name is 'German (formal)', we want just 'Formal'??
             # User requested:
             # German (Deutsch)
             # ↳ Formal
             # ↳ Informal
             
             # Let's check settings for 'variant_label' or parse 'name'
             variant_label = info.get('variant_label', info['name'])
             
             variant_entry = {
                 'code': code,
                 'name': variant_label, 
                 'styled_name': variant_label, # Variants usually just show the variant name
             }
             grouped[variant_of]['variants'].append(variant_entry)

    # Convert to list and sort
    result_list = list(grouped.values())
    
    # Sort by translated name in CURRENT locale
    def sort_key(item):
        return item['name_translated'].lower()
        
    result_list.sort(key=sort_key)
    
    # Pin current locale to the top
    if current_locale:
        # Normalize current_locale (e.g. 'en-us' -> 'en') if exact match not found?
        # Or just look for exact match first.
        # The 'code' in result_list matches keys in _LANGUAGES_CONFIG (e.g. 'en', 'de', 'zh-hans')
        
        # Try to find the item
        pinned_item = None
        for i, item in enumerate(result_list):
            if item['code'] == current_locale:
                pinned_item = result_list.pop(i)
                break
        
        if pinned_item:
            result_list.insert(0, pinned_item)
            
    return result_list
