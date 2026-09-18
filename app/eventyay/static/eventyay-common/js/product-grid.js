/**
 * Product grid exclusivity: "All products" cannot be combined with other picks.
 * Reuses the shared language-grid widget markup/behaviour for search, badges, and deselect.
 */
function dispatchCheckboxChange(checkbox) {
  checkbox.dispatchEvent(new Event('change', { bubbles: true }));
}

function initProductGridExclusivity(widget) {
  if (widget.dataset.productGridExclusiveInit === 'true') return;

  const grid = widget.querySelector('[data-language-grid-grid]');
  if (!grid) return;

  widget.dataset.productGridExclusiveInit = 'true';
  const allCell = grid.querySelector('[data-product-grid-all]');
  const allCheckbox = allCell?.querySelector('input[type="checkbox"]');
  if (!allCheckbox) return;

  const otherCheckboxes = Array.from(grid.querySelectorAll('[data-language-grid-cell] input[type="checkbox"]')).filter(
    (checkbox) => checkbox !== allCheckbox
  );

  grid.addEventListener('change', (event) => {
    const target = event.target;
    if (!target || target.type !== 'checkbox') return;

    if (target === allCheckbox && allCheckbox.checked) {
      otherCheckboxes.forEach((checkbox) => {
        if (checkbox.checked) {
          checkbox.checked = false;
          dispatchCheckboxChange(checkbox);
        }
      });
      return;
    }

    if (target !== allCheckbox && target.checked && allCheckbox.checked) {
      allCheckbox.checked = false;
      dispatchCheckboxChange(allCheckbox);
    }
  });
}

export function initAllProductGrids() {
  document.querySelectorAll('[data-product-grid-widget]').forEach(initProductGridExclusivity);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAllProductGrids);
} else {
  initAllProductGrids();
}

window.addEventListener('load', initAllProductGrids);
