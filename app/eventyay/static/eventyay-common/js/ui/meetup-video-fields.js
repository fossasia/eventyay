function updateVideoUrlVisibility(typeSelect, urlGroup) {
  if (typeSelect.value) {
    urlGroup.removeAttribute('hidden');
  } else {
    urlGroup.setAttribute('hidden', '');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const typeSelect = document.querySelector('[name="basics-video_type"]') || document.querySelector('[name="settings-video_type"]');
  const urlGroup = document.getElementById('video-url-group');

  if (!typeSelect || !urlGroup) {
    return;
  }

  updateVideoUrlVisibility(typeSelect, urlGroup);

  typeSelect.addEventListener('change', () => {
    updateVideoUrlVisibility(typeSelect, urlGroup);
  });
});
