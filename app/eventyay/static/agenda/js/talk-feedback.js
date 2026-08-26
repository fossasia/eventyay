/**
 * Session talk feedback UI: replies, reactions, ratings, and toggles.
 */
export function initTalkFeedback(root = document) {
  const replyBtns = root.querySelectorAll('.reply-btn');
  replyBtns.forEach((btn) => {
    if (btn.dataset.talkFeedbackInit === 'true') {
      return;
    }
    btn.dataset.talkFeedbackInit = 'true';
    btn.addEventListener('click', function () {
      const formId = this.getAttribute('data-form-id') || this.getAttribute('data-id');
      const parentId = this.getAttribute('data-parent-id') || this.getAttribute('data-id');
      const formContainer = root.getElementById
        ? root.getElementById('reply-form-' + formId)
        : document.getElementById('reply-form-' + formId);
      if (!formContainer) {
        return;
      }
      const replyItem = this.closest('.reply-item');
      if (replyItem) {
        replyItem.parentNode.insertBefore(formContainer, replyItem.nextSibling);
      } else {
        const actionsContainer = this.closest('.comment-actions');
        if (actionsContainer) {
          actionsContainer.parentNode.insertBefore(formContainer, actionsContainer.nextSibling);
        }
      }
      const parentInput = formContainer.querySelector('input[name="parent"]');
      if (parentInput && parentId) {
        parentInput.value = parentId;
      }
      formContainer.classList.remove('d-none');
      formContainer.style.display = 'block';
      const textarea = formContainer.querySelector('textarea');
      if (textarea) {
        textarea.focus();
      }
    });
  });

  const reactBtns = root.querySelectorAll('.react-btn');
  reactBtns.forEach((btn) => {
    if (btn.dataset.talkFeedbackReactInit === 'true') {
      return;
    }
    btn.dataset.talkFeedbackReactInit = 'true';
    btn.addEventListener('click', function () {
      let action = this.getAttribute('data-action');
      if (this.classList.contains('active-vote')) {
        action = 'remove';
      }
      const url = this.getAttribute('data-url');
      const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
      if (!csrfInput) {
        return;
      }
      const csrfToken = csrfInput.value;
      const container = this.closest('.d-flex');

      const formData = new FormData();
      formData.append('action', action);

      fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
        },
        body: formData,
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.error) {
            alert(data.error);
            return;
          }

          const upvoteBtn = container.querySelector('[data-action="upvote"]');
          const downvoteBtn = container.querySelector('[data-action="downvote"]');
          const upvoteIcon = upvoteBtn.querySelector('i');
          const downvoteIcon = downvoteBtn.querySelector('i');

          upvoteBtn.classList.remove('active-vote');
          upvoteIcon.className = 'fa fa-thumbs-o-up';
          downvoteBtn.classList.remove('active-vote');
          downvoteIcon.className = 'fa fa-thumbs-o-down';

          if (action === 'upvote') {
            upvoteBtn.classList.add('active-vote');
            upvoteIcon.className = 'fa fa-thumbs-up text-success';
          } else if (action === 'downvote') {
            downvoteBtn.classList.add('active-vote');
            downvoteIcon.className = 'fa fa-thumbs-down text-danger';
          }

          container.querySelector('.upvote-count').textContent = data.upvotes;
          container.querySelector('.downvote-count').textContent = data.downvotes;
        })
        .catch((error) => {
          console.error('Talk feedback reaction failed', error);
        });
    });
  });

  const starContainers = root.querySelectorAll('.youtube-rating-stars');
  starContainers.forEach((container) => {
    if (container.dataset.talkFeedbackStarsInit === 'true') {
      return;
    }
    container.dataset.talkFeedbackStarsInit = 'true';
    const labels = Array.from(container.querySelectorAll('.star-label'));

    function updateStars(index) {
      labels.forEach((lbl, i) => {
        if (i <= index) {
          lbl.classList.add('active');
        } else {
          lbl.classList.remove('active');
        }
      });
    }

    labels.forEach((label, index) => {
      label.addEventListener('mouseover', () => {
        updateStars(index);
      });

      label.addEventListener('click', () => {
        labels.forEach((lbl) => lbl.classList.remove('selected'));
        label.classList.add('selected');
        const radio = label.querySelector('input[type="radio"]');
        if (radio) {
          radio.checked = true;
        }
      });
    });

    container.addEventListener('mouseleave', () => {
      labels.forEach((lbl) => lbl.classList.remove('active'));
      const selectedIndex = labels.findIndex((lbl) => lbl.classList.contains('selected'));
      if (selectedIndex !== -1) {
        updateStars(selectedIndex);
      }
    });

    const initialSelected = labels.findIndex((lbl) => lbl.classList.contains('selected'));
    if (initialSelected !== -1) {
      updateStars(initialSelected);
    }
  });

  root.querySelectorAll('.reply-form-container').forEach((form) => {
    form.style.display = 'none';
  });

  root.querySelectorAll('.comment-text-collapsed').forEach((content) => {
    if (content.dataset.talkFeedbackReadMoreInit === 'true') {
      return;
    }
    if (content.scrollHeight <= content.clientHeight) {
      return;
    }
    const btn = content.nextElementSibling;
    if (!btn || !btn.classList.contains('read-more-btn')) {
      return;
    }
    content.dataset.talkFeedbackReadMoreInit = 'true';
    btn.classList.remove('d-none');
    btn.addEventListener('click', function () {
      const expanded = this.getAttribute('data-expanded') === 'true';
      const readMoreText = this.getAttribute('data-read-more');
      const showLessText = this.getAttribute('data-show-less');

      if (expanded) {
        content.classList.add('comment-text-collapsed');
        this.textContent = readMoreText;
        this.setAttribute('data-expanded', 'false');
      } else {
        content.classList.remove('comment-text-collapsed');
        this.textContent = showLessText;
        this.setAttribute('data-expanded', 'true');
      }
    });
  });

  root.querySelectorAll('.replies-toggle-btn').forEach((btn) => {
    if (btn.dataset.talkFeedbackRepliesInit === 'true') {
      return;
    }
    btn.dataset.talkFeedbackRepliesInit = 'true';
    btn.addEventListener('click', function () {
      const targetId = this.getAttribute('data-target');
      const target = document.getElementById(targetId);
      if (!target) {
        return;
      }
      target.classList.toggle('d-none');
      const expanded = this.getAttribute('data-expanded') === 'true';
      const icon = this.querySelector('i');
      if (expanded) {
        this.setAttribute('data-expanded', 'false');
        icon.classList.remove('fa-caret-up');
        icon.classList.add('fa-caret-down');
      } else {
        this.setAttribute('data-expanded', 'true');
        icon.classList.remove('fa-caret-down');
        icon.classList.add('fa-caret-up');
      }
    });
  });

  root.querySelectorAll('[data-confirm-message]').forEach((button) => {
    if (button.dataset.talkFeedbackConfirmInit === 'true') {
      return;
    }
    button.dataset.talkFeedbackConfirmInit = 'true';
    button.addEventListener('click', function (event) {
      const message = this.getAttribute('data-confirm-message');
      if (message && !window.confirm(message)) {
        event.preventDefault();
      }
    });
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => initTalkFeedback());
} else {
  initTalkFeedback();
}
