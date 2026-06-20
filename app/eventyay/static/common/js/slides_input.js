document.addEventListener('DOMContentLoaded', function() {
  var widgets = document.querySelectorAll('.slides-input-widget');
  widgets.forEach(function(widget) {
    var id = widget.getAttribute('data-id');
    var isReRender = widget.getAttribute('data-is-re-render') === 'true';
    
    var input = document.getElementById(id);
    var label = document.getElementById(id + '_label');
    var errorMsg = document.getElementById(id + '_error');
    var storageWarningMsg = document.getElementById(id + '_storage_warning');
    var storageKey = 'file_upload_' + id;
    
    function b64toFile(b64Data, contentType, filename) {
        var sliceSize = 512;
        var byteCharacters = atob(b64Data);
        var byteArrays = [];
        for (var offset = 0; offset < byteCharacters.length; offset += sliceSize) {
            var slice = byteCharacters.slice(offset, offset + sliceSize);
            var byteNumbers = new Array(slice.length);
            for (var i = 0; i < slice.length; i++) {
                byteNumbers[i] = slice.charCodeAt(i);
            }
            var byteArray = new Uint8Array(byteNumbers);
            byteArrays.push(byteArray);
        }
        var blob = new Blob(byteArrays, {type: contentType});
        return new File([blob], filename, {type: contentType});
    }

    if (input && label) {
      label.dataset.original = label.textContent.trim();
      
      // Restore from sessionStorage on load if re-rendering due to errors
      try {
          if (isReRender) {
              var storedData = sessionStorage.getItem(storageKey);
              if (storedData) {
                  var dataArr = JSON.parse(storedData);
                  var dt = new DataTransfer();
                  var names = [];
                  dataArr.forEach(function(data) {
                      var file = b64toFile(data.base64, data.type, data.name);
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

      input.addEventListener('change', function() {
        if (input.files && input.files.length > 0) {
          var maxSize = parseInt(input.getAttribute('data-maxsize'), 10);
          var exceedsMaxSize = false;
          
          if (maxSize) {
            for (var i = 0; i < input.files.length; i++) {
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
          var names = Array.from(input.files).map(function(f) { return f.name; });
          label.textContent = names.join(', ');
          label.classList.remove('text-muted');

          // Save to sessionStorage
          var filesData = [];
          var filesToProcess = input.files.length;
          var processed = 0;
          
          Array.from(input.files).forEach(function(file) {
              var reader = new FileReader();
              reader.onload = function(e) {
                  var base64 = e.target.result.split(',')[1];
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
