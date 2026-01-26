import random


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


def generate_random_high_contrast_color(min_contrast=2.5, max_attempts=100, exclude_colors=None):
    """Generate a random hex color with sufficient contrast against white background."""
    white = (255, 255, 255)
    exclude_colors = exclude_colors or set()
    exclude_colors = {color.lower() for color in exclude_colors}
    
    for _ in range(max_attempts):
        r = random.randint(30, 220)
        g = random.randint(30, 220)
        b = random.randint(30, 220)
        
        color_hex = f'#{r:02x}{g:02x}{b:02x}'
        
        # Skip if color is already used
        if color_hex.lower() in exclude_colors:
            continue
        
        contrast = calculate_contrast_ratio((r, g, b), white)
        
        if contrast >= min_contrast:
            return color_hex
    
    return '#336699'
