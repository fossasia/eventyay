/**
 * Updates the product import preview when mapping or create-missing toggle changes.
 */
function renderProductPreview(previewData, productMapping, createMissing, labels) {
  const container = document.getElementById('product-import-preview-body');
  if (!container) {
    return;
  }

  const items = previewData[productMapping] || [];
  container.replaceChildren();
  if (!items) {
    appendMessage(container, labels.empty_values, 'text-muted');
    return;
  }

  const matched = items.filter((item) => item.status === 'matched');
  const ambiguous = items.filter((item) => item.status === 'ambiguous');
  const unmatched = items.filter((item) => item.status === 'create' || item.status === 'missing');

  if (matched.length) {
    appendTableSection(
      container,
      labels.matched_heading,
      'text-success',
      [labels.col_csv_value, labels.col_matched_product, labels.col_rows],
      matched.map((item) => [item.csv_value, item.product_label, item.rows]),
    );
  }

  if (unmatched.length) {
    const heading = createMissing ? labels.create_heading : labels.missing_heading;
    appendTableSection(
      container,
      heading,
      createMissing ? 'text-info' : 'text-danger',
      [labels.col_csv_value, labels.col_result, labels.col_rows],
      unmatched.map((item) => [
        item.csv_value,
        createMissing ? labels.result_will_create : labels.result_no_match,
        item.rows,
      ]),
    );
  }

  if (ambiguous.length) {
    appendTableSection(
      container,
      labels.ambiguous_heading,
      'text-warning',
      [labels.col_csv_value, labels.col_matching_products, labels.col_rows],
      ambiguous.map((item) => [item.csv_value, item.product_label, item.rows]),
    );
  }

  if (!matched.length && !unmatched.length && !ambiguous.length) {
    appendMessage(container, labels.empty_values, 'text-muted');
  }
}

function appendMessage(container, text, className) {
  const message = document.createElement('p');
  message.className = className;
  message.textContent = text;
  container.appendChild(message);
}

function appendTableSection(container, headingText, headingClass, headers, rows) {
  const heading = document.createElement('h4');
  heading.className = headingClass;
  heading.textContent = headingText;
  container.appendChild(heading);

  const table = document.createElement('table');
  table.className = 'table table-condensed table-striped';

  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  headers.forEach((headerText, index) => {
    const th = document.createElement('th');
    if (index === headers.length - 1) {
      th.className = 'text-right';
    }
    th.textContent = headerText;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  rows.forEach((row) => {
    const tr = document.createElement('tr');
    row.forEach((cellValue, index) => {
      const td = document.createElement('td');
      if (index === row.length - 1) {
        td.className = 'text-right';
      }
      td.textContent = String(cellValue ?? '');
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  container.appendChild(table);
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
