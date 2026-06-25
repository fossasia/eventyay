$(function() {
    var cropper = null;
    var currentInput = null;

    var $modal = $('#cropperModal');
    var image = document.getElementById('cropperImage');
    var $saveBtn = $('#cropperSaveBtn');

    var cropApplied = false;

    var config = {
        'id_settings-event_logo_image': { ratio: NaN }, // Free form aspect ratio for Logo
        'id_settings-logo_image': { ratio: 1920 / 640 } // 3:1 aspect ratio for Header Image (recommended 1920x640)
    };

    function initCropperForInput(inputId) {
        var $input = $('#' + inputId);
        if ($input.length === 0) return;

        // Insert hidden fields right after the input
        var fieldName = $input.attr('name');
        var hiddenFields = `
            <input type="hidden" name="${fieldName}_crop_x" id="id_${fieldName}_crop_x">
            <input type="hidden" name="${fieldName}_crop_y" id="id_${fieldName}_crop_y">
            <input type="hidden" name="${fieldName}_crop_w" id="id_${fieldName}_crop_w">
            <input type="hidden" name="${fieldName}_crop_h" id="id_${fieldName}_crop_h">
        `;
        $input.after(hiddenFields);


        $input.on('change', function(e) {
            var files = e.target.files;
            if (files && files.length > 0) {
                var file = files[0];
                if (!file.type.startsWith('image/')) return;
                
                // Bypass cropper for GIFs to preserve animations (backend skips optimization for animated GIFs anyway)
                if (file.type === 'image/gif') {
                    return;
                }
                
                cropApplied = false;
                currentInput = inputId;
                var reader = new FileReader();
                reader.onload = function(evt) {
                    image.src = evt.target.result;
                    
                    $modal.modal({ backdrop: 'static', keyboard: false });
                    
                    $modal.one('shown.bs.modal', function() {
                        if (cropper) {
                            cropper.destroy();
                        }
                        cropper = new Cropper(image, {
                            aspectRatio: config[inputId].ratio,
                            viewMode: 1,
                        });
                    });
                };
                reader.readAsDataURL(file);
            }
        });
    }

    initCropperForInput('id_settings-event_logo_image');
    initCropperForInput('id_settings-logo_image');

    $modal.on('hidden.bs.modal', function() {
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
        if (!cropApplied && currentInput) {
            // If the user cancelled, clear the file input so the uncropped image isn't saved.
            $('#' + currentInput).val('');
        }
        currentInput = null;
    });

    $saveBtn.on('click', function() {
        if (cropper && currentInput) {
            cropApplied = true;
            var cropData = cropper.getData(true);
            var $input = $('#' + currentInput);
            var fieldName = $input.attr('name');
            
            // Construct the hidden field ID based on the input name
            // The name is usually "settings-event_logo_image", so hidden field ID is "id_settings-event_logo_image_crop_x"
            $('#id_' + fieldName + '_crop_x').val(cropData.x);
            $('#id_' + fieldName + '_crop_y').val(cropData.y);
            $('#id_' + fieldName + '_crop_w').val(cropData.width);
            $('#id_' + fieldName + '_crop_h').val(cropData.height);

            // Persist the preview directly into the form's existing thumbnail
            var canvas = cropper.getCroppedCanvas();
            if (canvas) {
                var dataUrl = canvas.toDataURL();
                var $container = $input.closest('[class*="col-"]');
                if ($container.length === 0) {
                    $container = $input.parent();
                }
                
                var imgStyles = {
                    maxWidth: '100%',
                    maxHeight: '150px',
                    width: 'auto',
                    objectFit: 'contain',
                    display: 'block',
                    marginBottom: '10px'
                };

                var $existingImg = $container.find('img').first();
                if ($existingImg.length) {
                    $existingImg.attr('src', dataUrl).css(imgStyles);
                    $existingImg.removeAttr('srcset');
                    if ($existingImg.parent().is('a')) {
                        $existingImg.parent().attr('href', dataUrl);
                    }
                } else {
                    var $newImg = $('<img>').attr('src', dataUrl).css(imgStyles);
                    $newImg.insertBefore($input);
                }
            }

            $modal.modal('hide');
        }
    });
});
