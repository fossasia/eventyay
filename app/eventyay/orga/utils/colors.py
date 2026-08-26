import random

RGB_MIN, RGB_MAX = 30, 220
WHITE_RGB = (255, 255, 255)


def calculate_luminance(r, g, b):
    """Calculate relative luminance for an RGB color (WCAG 2.1)."""
    def normalize(value):
        value = value / 255.0
        if value <= 0.03928:
            return value / 12.92
        return ((value + 0.055) / 1.055) ** 2.4

    r = normalize(r)
    g = normalize(g)
    b = normalize(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def calculate_contrast_ratio(rgb1, rgb2):
    """Calculate contrast ratio between two RGB colors (WCAG 2.1)."""
    l1 = calculate_luminance(rgb1[0], rgb1[1], rgb1[2]) + 0.05
    l2 = calculate_luminance(rgb2[0], rgb2[1], rgb2[2]) + 0.05
    if l1 > l2:
        return l1 / l2
    return l2 / l1


BLACK_RGB = (0, 0, 0)


def get_contrast_color(hex_color):
    """Return 'black' or 'white' text color for a hex background, using WCAG 2.1 contrast ratios."""
    if not hex_color:
        return ''
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(c + c for c in hex_color)
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    except ValueError:
        return ''
    contrast_with_white = calculate_contrast_ratio((r, g, b), WHITE_RGB)
    contrast_with_black = calculate_contrast_ratio((r, g, b), BLACK_RGB)
    return 'white' if contrast_with_white >= contrast_with_black else 'black'


def generate_random_high_contrast_color(min_contrast=3.0, max_attempts=100, exclude_colors=None):
    """Generate a random hex color with sufficient contrast against white background."""
    exclude_colors = exclude_colors or set()
    exclude_set = {color.lower() for color in exclude_colors if isinstance(color, str) and color}

    for _ in range(max_attempts):
        r = random.randint(RGB_MIN, RGB_MAX)
        g = random.randint(RGB_MIN, RGB_MAX)
        b = random.randint(RGB_MIN, RGB_MAX)

        color_hex = f'#{r:02x}{g:02x}{b:02x}'

        if color_hex.lower() in exclude_set:
            continue

        contrast = calculate_contrast_ratio((r, g, b), WHITE_RGB)

        if contrast >= min_contrast:
            return color_hex

    # Fallback colors (pre-verified to meet default min_contrast against white)
    fallback_colors = ['#336699', '#993333', '#663399', '#1e3a5f', '#4a90a4']
    for fallback in fallback_colors:
        if fallback.lower() in exclude_set:
            continue
        fr = int(fallback[1:3], 16)
        fg = int(fallback[3:5], 16)
        fb = int(fallback[5:7], 16)
        contrast = calculate_contrast_ratio((fr, fg, fb), WHITE_RGB)
        if contrast >= min_contrast:
            return fallback

    raise ValueError(
        f"Unable to generate a color with min_contrast={min_contrast} "
        f"after {max_attempts} attempts and checking fallbacks."
    )
