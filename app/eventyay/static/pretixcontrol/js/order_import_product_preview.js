/**
 * Updates the product import preview when mapping or create-missing toggle changes.
 */
function renderProductPreview(previewData, productMapping, createMissing, labels) {
  const container = document.getElementById('product-import-preview-body');
  if (!container) {
    return;
  }

  const items = previewData[productMapping];
  if (!items) {
    container.innerHTML = '';
    return;
  }

  const matched = items.filter((item) => item.status === 'matched');
  const ambiguous = items.filter((item) => item.status === 'ambiguous');
  const unmatched = items.filter((item) => item.status === 'create' || item.status === 'missing');

  let html = '';

  if (matched.length) {
    html += '<h4 class="text-success">' + escapeHtml(labels.matched_heading) + '</h4>';
    html += '<table class="table table-condensed table-striped"><thead><tr>';
    html += '<th>' + escapeHtml(labels.col_csv_value) + '</th>';
    html += '<th>' + escapeHtml(labels.col_matched_product) + '</th>';
    html += '<th class="text-right">' + escapeHtml(labels.col_rows) + '</th></tr></thead><tbody>';
    matched.forEach((item) => {
      html += '<tr><td>' + escapeHtml(item.csv_value) + '</td>';
      html += '<td>' + escapeHtml(item.product_label) + '</td>';
      html += '<td class="text-right">' + item.rows + '</td></tr>';
    });
    html += '</tbody></table>';
  }

  if (unmatched.length) {
    const heading = createMissing ? labels.create_heading : labels.missing_heading;
    const headingClass = createMissing ? 'text-info' : 'text-danger';
    html += '<h4 class="' + headingClass + '">' + escapeHtml(heading) + '</h4>';
    html += '<table class="table table-condensed table-striped"><thead><tr>';
    html += '<th>' + escapeHtml(labels.col_csv_value) + '</th>';
    html += '<th>' + escapeHtml(labels.col_result) + '</th>';
    html += '<th class="text-right">' + escapeHtml(labels.col_rows) + '</th></tr></thead><tbody>';
    unmatched.forEach((item) => {
      const result = createMissing ? labels.result_will_create : labels.result_no_match;
      html += '<tr><td>' + escapeHtml(item.csv_value) + '</td>';
      html += '<td>' + escapeHtml(result) + '</td>';
      html += '<td class="text-right">' + item.rows + '</td></tr>';
    });
    html += '</tbody></table>';
  }

  if (ambiguous.length) {
    html += '<h4 class="text-warning">' + escapeHtml(labels.ambiguous_heading) + '</h4>';
    html += '<table class="table table-condensed table-striped"><thead><tr>';
    html += '<th>' + escapeHtml(labels.col_csv_value) + '</th>';
    html += '<th>' + escapeHtml(labels.col_matching_products) + '</th>';
    html += '<th class="text-right">' + escapeHtml(labels.col_rows) + '</th></tr></thead><tbody>';
    ambiguous.forEach((item) => {
      html += '<tr><td>' + escapeHtml(item.csv_value) + '</td>';
      html += '<td>' + escapeHtml(item.product_label) + '</td>';
      html += '<td class="text-right">' + item.rows + '</td></tr>';
    });
    html += '</tbody></table>';
  }

  if (!matched.length && !unmatched.length && !ambiguous.length) {
    html = '<p class="text-muted">' + escapeHtml(labels.empty_values) + '</p>';
  }

  container.innerHTML = html;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function initProductImportPreview() {
  const dataElement = document.getElementById('product-import-preview-data');
  const labelsElement = document.getElementById('product-import-preview-labels');
  const productField = document.getElementById('id_product');
  const createMissingField = document.getElementById('id_create_missing_products');

  if (!dataElement || !labelsElement || !productField) {
    return;
  }

  let previewData;
  let labels;
  try {
    previewData = JSON.parse(dataElement.textContent);
    labels = JSON.parse(labelsElement.textContent);
  } catch (e) {
    return;
  }

  function update() {
    const createMissing = createMissingField ? createMissingField.checked : false;
    renderProductPreview(previewData, productField.value, createMissing, labels);
  }

  productField.addEventListener('change', update);
  if (createMissingField) {
    createMissingField.addEventListener('change', update);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initProductImportPreview);
} else {
  initProductImportPreview();
}
