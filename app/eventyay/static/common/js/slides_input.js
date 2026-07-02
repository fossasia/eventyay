document.addEventListener('DOMContentLoaded', () => {
  const widgets = document.querySelectorAll('.slides-input-widget');
  widgets.forEach(widget => {
    const id = widget.getAttribute('data-id');
    const isReRender = widget.getAttribute('data-is-re-render') === 'true';

    const input = document.getElementById(id);
    const label = document.getElementById(id + '_label');
    const errorMsg = document.getElementById(id + '_error');
    const storageWarningMsg = document.getElementById(id + '_storage_warning');
    const storageKey = 'file_upload_' + id;

    function b64toFile(b64Data, contentType, filename) {
        const sliceSize = 512;
        const byteCharacters = atob(b64Data);
        const byteArrays = [];
        for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
            const slice = byteCharacters.slice(offset, offset + sliceSize);
            const byteNumbers = new Array(slice.length);
            for (let i = 0; i < slice.length; i++) {
                byteNumbers[i] = slice.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            byteArrays.push(byteArray);
        }
        const blob = new Blob(byteArrays, {type: contentType});
        return new File([blob], filename, {type: contentType});
    }

    if (input && label) {
      label.dataset.original = label.textContent.trim();

      // Restore from sessionStorage on load if re-rendering due to errors
      try {
          if (isReRender) {
              const storedData = sessionStorage.getItem(storageKey);
              if (storedData) {
                  const dataArr = JSON.parse(storedData);
                  const dt = new DataTransfer();
                  const names = [];
                  dataArr.forEach(data => {
                      const file = b64toFile(data.base64, data.type, data.name);
                      dt.items.add(file);
                      names.push(data.name);
                  });
                  input.files = dt.files;
                  label.textContent = names.join(', ');
                  label.classList.remove('text-muted');
              }
          } else {
              sessionStorage.removeItem(storageKey);
          }
      } catch (e) {
          console.warn('Failed to restore or clear files in sessionStorage', e);
      }

      input.addEventListener('change', () => {
        if (input.files && input.files.length > 0) {
          const maxSize = parseInt(input.getAttribute('data-maxsize'), 10);
          let exceedsMaxSize = false;

          if (maxSize) {
            for (let i = 0; i < input.files.length; i++) {
              if (input.files[i].size > maxSize) {
                exceedsMaxSize = true;
                break;
              }
            }
          }

          if (exceedsMaxSize) {
            // Show error, clear input
            errorMsg.style.display = 'block';
            if (storageWarningMsg) {
              storageWarningMsg.style.display = 'none';
            }
            input.value = '';
            label.textContent = label.dataset.original;
            label.classList.add('text-muted');
            try { sessionStorage.removeItem(storageKey); } catch(e) {}
            return;
          }

          errorMsg.style.display = 'none';
          if (storageWarningMsg) {
            storageWarningMsg.style.display = 'none';
          }
          const names = Array.from(input.files).map(f => f.name);
          label.textContent = names.join(', ');
          label.classList.remove('text-muted');

          // Proactively skip base64 storage if size > 2MB
          const totalSize = Array.from(input.files).reduce((acc, file) => acc + file.size, 0);
          if (totalSize > 2 * 1024 * 1024) {
              console.warn('Files too large for sessionStorage (> 2MB)');
              if (storageWarningMsg) {
                  storageWarningMsg.style.display = 'block';
              }
              try { sessionStorage.removeItem(storageKey); } catch(e) {}
              return;
          }

          // Save to sessionStorage
          const filesData = [];
          const filesToProcess = input.files.length;
          let processed = 0;

          Array.from(input.files).forEach(file => {
              const reader = new FileReader();
              reader.onload = e => {
                  const base64 = e.target.result.split(',')[1];
                  filesData.push({
                      name: file.name,
                      type: file.type,
                      base64: base64
                  });
                  processed++;
                  if (processed === filesToProcess) {
                      try {
                          sessionStorage.setItem(storageKey, JSON.stringify(filesData));
                          if (storageWarningMsg) {
                            storageWarningMsg.style.display = 'none';
                          }
                      } catch (err) {
                          console.warn('Files too large for sessionStorage', err);
                          if (storageWarningMsg) {
                            storageWarningMsg.style.display = 'block';
                          }
                      }
                  }
              };
              reader.readAsDataURL(file);
          });
        } else {
          errorMsg.style.display = 'none';
          if (storageWarningMsg) {
            storageWarningMsg.style.display = 'none';
          }
          label.textContent = label.dataset.original;
          label.classList.add('text-muted');
          try { sessionStorage.removeItem(storageKey); } catch(e) {}
        }
      });
    }
  });
});
