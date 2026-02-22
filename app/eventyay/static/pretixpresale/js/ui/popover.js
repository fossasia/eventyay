const BASE_PATH_ID = 'base_path';
const ORGANIZER_NAME_ID = 'organizer_name';
const EVENT_SLUG_ID = 'event_slug';
const SHOW_ORGANIZER_AREA_ID = 'show_organizer_area';
const HAS_SUBMISSIONS_ID = 'has_submissions';
const TALK_COMPONENT_PUBLISHED_ID = 'talk_component_published';

function getJson(id, fallback = null) {
  const el = document.getElementById(id);
  return el ? JSON.parse(el.textContent) : fallback;
}

$(function () {
  const basePath = getJson(BASE_PATH_ID, null);
  if (basePath === null || basePath === undefined) {
    console.error(`JSON element ${BASE_PATH_ID} missing`);
    return;
  }

  const options = {
    html: true,
    content: `
      <div data-name="popover-content">
        <div class="options">
          <a href="${basePath}" target="_self" class="btn btn-outline-success">
            <i class="fa fa-ticket"></i> ${window.gettext('Tickets')}
          </a>
        </div>
        <div class="options">
          <a href="${basePath}/common/orders/" target="_self" class="btn btn-outline-success">
            <i class="fa fa-shopping-cart"></i> ${window.gettext('My orders')}
          </a>
        </div>
      </div>
    `,
    placement: 'bottom',
    trigger: 'manual'
  };

  $('[data-toggle="popover"]').popover(options).click(function (e) {
    e.stopPropagation();
    $(this).popover('show');
    $('[data-toggle="popover-profile"]').popover('hide');
  });
});

$(function () {
  const basePath = getJson(BASE_PATH_ID, null);
  if (basePath === null || basePath === undefined) {
    console.error(`JSON element ${BASE_PATH_ID} missing`);
    return;
  }

  const organizerName = getJson(ORGANIZER_NAME_ID, '');
  const eventSlug = getJson(EVENT_SLUG_ID, '');
  const showOrganizerArea = getJson(SHOW_ORGANIZER_AREA_ID, false);
  const hasSubmissions = getJson(HAS_SUBMISSIONS_ID, false);
  const talkComponentPublished = getJson(TALK_COMPONENT_PUBLISHED_ID, false);

  const currentPath = window.location.pathname + window.location.search;
  const logoutParams = new URLSearchParams({ back: currentPath });
  const logoutPath = `${basePath}/common/logout/?${logoutParams.toString()}`;

  const blocks = [
    `<div data-name="popover-profile-menu">`,
    `
    <div class="profile-menu">
      <a href="${basePath}/common/orders/" target="_self" class="btn btn-outline-success">
        <i class="fa fa-shopping-cart"></i> ${window.gettext('My orders')}
      </a>
    </div>
    `
  ];

  if (hasSubmissions && talkComponentPublished) {
    blocks.push(`
      <div class="profile-menu">
        <a href="${basePath}/${organizerName}/${eventSlug}/me/submissions/" target="_self" class="btn btn-outline-success">
          <i class="fa fa-sticky-note-o"></i> ${window.gettext('My proposals')}
        </a>
      </div>

      <div class="profile-menu">
        <a href="${basePath}/${organizerName}/${eventSlug}/me" target="_self" class="btn btn-outline-success">
          <i class="fa fa-address-card-o"></i> ${window.gettext('Speaker profile')}
        </a>
      </div>

      <div class="profile-menu">
        <a href="${basePath}/${organizerName}/${eventSlug}/me/mails/" target="_self" class="btn btn-outline-success">
          <i class="fa fa-envelope"></i> ${window.gettext('Speaker emails')}
        </a>
      </div>
    `);
  }

  blocks.push(`
    <div class="profile-menu">
      <a href="${basePath}/common/account/" target="_self" class="btn btn-outline-success">
        <i class="fa fa-user"></i> ${window.gettext('Account')}
      </a>
    </div>
  `);

  if (showOrganizerArea) {
    blocks.push(`
      <div class="profile-menu organizer-area">
        <a href="${basePath}/common/event/${organizerName}/${eventSlug}" target="_self" class="btn btn-outline-success">
          <i class="fa fa-gears"></i> ${window.gettext('Organizer area')}
        </a>
      </div>
    `);
  }

  blocks.push(`
    <div class="profile-menu">
      <a href="${logoutPath}" target="_self" class="btn btn-outline-success">
        <i class="fa fa-sign-out"></i> ${window.gettext('Logout')}
      </a>
    </div>
  </div>
  `);

  const options = {
    html: true,
    content: blocks.join('\n'),
    placement: 'bottom',
    trigger: 'manual'
  };

  $('[data-toggle="popover-profile"]').popover(options).click(function (e) {
    e.stopPropagation();
    $(this).popover('toggle');
  });
});

$('html').click(function () {
  $('[data-toggle="popover"]').popover('hide');
  $('[data-toggle="popover-profile"]').popover('hide');
});
