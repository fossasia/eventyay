/**
 * Theme settings management and live preview.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Get form field elements
  const primaryColorInput = document.getElementById('primary_color');
  const secondaryColorInput = document.getElementById('secondary_color');
  const colorModeInputs = document.querySelectorAll('input[name="color_mode"]');
  const inheritOrgThemeInput = document.getElementById('inherit_organizer_theme');
  const isActiveInput = document.getElementById('is_active');
  const customCssInput = document.getElementById('custom_css');
  const descriptionInput = document.getElementById('description');

  // Get preview elements
  const themePreview = document.getElementById('theme-preview');

  /**
   * Update the live preview with current colors
   */
  const updatePreview = () => {
    const primary = primaryColorInput?.value || '#EB2188';
    const secondary = secondaryColorInput?.value || '#3B82F6';

    // Update CSS variables in the preview section
    if (themePreview) {
      themePreview.style.setProperty('--color-primary', primary);
      themePreview.style.setProperty('--color-secondary', secondary);
    }

    // Also apply to document root for real-time preview
    document.documentElement.style.setProperty('--color-primary', primary);
    document.documentElement.style.setProperty('--color-secondary', secondary);
  };

  /**
   * Sync text inputs with color inputs
   */
  const syncTextInputs = () => {
    const primaryHex = primaryColorInput?.value || '#EB2188';
    const secondaryHex = secondaryColorInput?.value || '#3B82F6';

    const primaryText = document.getElementById('primary_color_text');
    const secondaryText = document.getElementById('secondary_color_text');

    if (primaryText) primaryText.value = primaryHex;
    if (secondaryText) secondaryText.value = secondaryHex;
  };

  // Bind event listeners for color inputs
  if (primaryColorInput) {
    primaryColorInput.addEventListener('input', () => {
      syncTextInputs();
      updatePreview();
    });
  }

  if (secondaryColorInput) {
    secondaryColorInput.addEventListener('input', () => {
      syncTextInputs();
      updatePreview();
    });
  }

  // Bind event listeners for text inputs
  const primaryText = document.getElementById('primary_color_text');
  const secondaryText = document.getElementById('secondary_color_text');

  if (primaryText) {
    primaryText.addEventListener('change', (e) => {
      if (primaryColorInput && /^#[0-9A-Fa-f]{6}$/.test(e.target.value)) {
        primaryColorInput.value = e.target.value;
        updatePreview();
      }
    });
  }

  if (secondaryText) {
    secondaryText.addEventListener('change', (e) => {
      if (secondaryColorInput && /^#[0-9A-Fa-f]{6}$/.test(e.target.value)) {
        secondaryColorInput.value = e.target.value;
        updatePreview();
      }
    });
  }

  // Export functionality
  document.getElementById('export-btn')?.addEventListener('click', () => {
    const theme = {
      primaryColor: primaryColorInput?.value || '#EB2188',
      secondaryColor: secondaryColorInput?.value || '#3B82F6',
      colorMode: Array.from(colorModeInputs).find(r => r.checked)?.value || 'auto',
      description: descriptionInput?.value || '',
      inheritOrganizerTheme: inheritOrgThemeInput?.checked || false,
      isActive: isActiveInput?.checked ?? true,
      customCSS: customCssInput?.value || '',
    };

    const json = JSON.stringify(theme, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'theme-backup.json';
    a.click();
    URL.revokeObjectURL(url);
  });

  // Import functionality
  document.getElementById('import-btn')?.addEventListener('click', () => {
    document.getElementById('theme-file-input')?.click();
  });

  const fileInput = document.getElementById('theme-file-input');
  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const theme = JSON.parse(event.target.result);
          if (theme.primaryColor && primaryColorInput) {
            primaryColorInput.value = theme.primaryColor;
          }
          if (theme.secondaryColor && secondaryColorInput) {
            secondaryColorInput.value = theme.secondaryColor;
          }
          if (theme.colorMode && colorModeInputs.length) {
            const modeInput = Array.from(colorModeInputs).find(input => input.value === theme.colorMode);
            if (modeInput) modeInput.checked = true;
          }
          if (theme.description !== undefined && descriptionInput) {
            descriptionInput.value = theme.description;
          }
          if (theme.inheritOrganizerTheme !== undefined && inheritOrgThemeInput) {
            inheritOrgThemeInput.checked = Boolean(theme.inheritOrganizerTheme);
          }
          if (theme.isActive !== undefined && isActiveInput) {
            isActiveInput.checked = Boolean(theme.isActive);
          }
          if (theme.customCSS !== undefined && customCssInput) {
            customCssInput.value = theme.customCSS;
          }
          syncTextInputs();
          updatePreview();
        } catch (error) {
          alert('Invalid JSON file format.');
          console.error('Import error:', error);
        }
      };
      reader.readAsText(file);
    });
  }

  // Initialize preview with current values
  syncTextInputs();
  updatePreview();
});
