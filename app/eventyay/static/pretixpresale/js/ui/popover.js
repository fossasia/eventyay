
const BASE_PATH_ID = 'base_path';
const ORGANIZER_NAME_ID = 'organizer_name';
const EVENT_SLUG_ID = 'event_slug';
const EVENT_PK_ID = 'event_pk';
const SHOW_ORGANIZER_AREA_ID = 'show_organizer_area';

$(function () {
  const basePathDefinition = document.getElementById(BASE_PATH_ID);
  const orgNameDefinition = document.getElementById(ORGANIZER_NAME_ID);
  const eventSlugDefinition = document.getElementById(EVENT_SLUG_ID);
  let basePath = '';
  if (basePathDefinition) {
    basePath = JSON.parse(basePathDefinition.textContent);
  } else {
    console.error(`JSON element to define ${BASE_PATH_ID} is missing!`)
    // This info is essential to build all items in the menu, so we can't continue without it.
    return;
  }
  let organizerName = '';
  if (orgNameDefinition) {
    organizerName = JSON.parse(orgNameDefinition.textContent);
  } else {
    console.warn(`JSON element to define ${ORGANIZER_NAME_ID} is missing!`)
  }
  let eventSlug = '';
  if (eventSlugDefinition) {
    eventSlug = JSON.parse(eventSlugDefinition.textContent);
  } else {
    console.warn(`JSON element to define ${EVENT_SLUG_ID} is missing!`)
  }
  const options = {
    html: true,
    content: `
      <div data-name="popover-content">
        <div class="options">
          <a href="${basePath}/${organizerName}/${eventSlug}" target="_self" class="btn btn-outline-success">
            <i class="fa fa-ticket"></i> ${window.gettext('Tickets')}
          </a>
        </div>
        <div class="options">
          <a href="${basePath}/common/orders/" target="_self" class="btn btn-outline-success">
            <i class="fa fa-shopping-cart"></i> ${window.gettext('My Orders')}
          </a>
        </div>
      </div>`,
    placement: 'bottom',
    trigger: 'manual'

  }
  $('[data-toggle="popover"]').popover(options).click(function (evt) {
    evt.stopPropagation();
    $(this).popover('show');
    $('[data-toggle="popover-profile"]').popover('hide');
  });
})

$(function () {
  const basePathDefinition = document.getElementById(BASE_PATH_ID);
  const orgNameDefinition = document.getElementById(ORGANIZER_NAME_ID);
  const eventSlugDefinition = document.getElementById(EVENT_SLUG_ID);
  const eventPkDefinition = document.getElementById(EVENT_PK_ID);
  const showOrganizerAreaDefinition = document.getElementById(SHOW_ORGANIZER_AREA_ID);
  let basePath = '';
  if (basePathDefinition) {
    basePath = JSON.parse(basePathDefinition.textContent);
  } else {
    console.error(`JSON element to define ${BASE_PATH_ID} is missing!`)
    // This info is essential to build the URL, so we can't continue without it.
    return;
  }
  let organizerName = '';
  if (orgNameDefinition) {
    organizerName = JSON.parse(orgNameDefinition.textContent);
  } else {
    console.warn(`JSON element to define ${ORGANIZER_NAME_ID} is missing!`)
  }
  let eventSlug = '';
  if (eventSlugDefinition) {
    eventSlug = JSON.parse(eventSlugDefinition.textContent);
  } else {
    console.warn(`JSON element to define ${EVENT_SLUG_ID} is missing!`)
  }
  let eventPk = '';
  if (eventPkDefinition) {
    eventPk = JSON.parse(eventPkDefinition.textContent);
  } else {
    console.warn(`JSON element to define ${EVENT_PK_ID} is missing!`)
  }
  let showOrganizerArea = false;
  if (showOrganizerAreaDefinition) {
    showOrganizerArea = JSON.parse(showOrganizerAreaDefinition.textContent);
  } else {
    console.warn(`JSON element to define ${SHOW_ORGANIZER_AREA_ID} is missing!`)
  }
  const hasCfpSubmissionsDefinition = document.getElementById('user_has_cfp_submissions');
  const talksPublishedDefinition = document.getElementById('talks_published');

  let hasCfpSubmissions = false;
  if (hasCfpSubmissionsDefinition) {
    hasCfpSubmissions = JSON.parse(hasCfpSubmissionsDefinition.textContent);
  }

  let talksPublished = false;
  if (talksPublishedDefinition) {
    talksPublished = JSON.parse(talksPublishedDefinition.textContent);
  }

  const currentPath = window.location.pathname;
  const queryString = window.location.search;

  const backUrl = `${currentPath}${queryString}`;

  // Constructing logout path using URLSearchParams
  const logoutParams = new URLSearchParams({ back: backUrl });
  const logoutPath = `/common/logout/?${logoutParams}`;

  const profilePath = '/common/account/';
  const orderPath = '/common/orders/';
  const ticketPath = eventPk !== '' ? `${orderPath}?event=${encodeURIComponent(eventPk)}` : orderPath;
  const dashboardPath = '/common/';

  const blocks = [
    `<div data-name="popover-profile-menu">
      <div class="profile-menu">
          <a href="${basePath}/" target="_self" class="btn btn-outline-success">
              <i class="fa fa-home"></i> ${window.gettext('Home')}
          </a>
      </div>
      <div class="profile-menu">
          <a href="${basePath}${dashboardPath}" target="_self" class="btn btn-outline-success">
              <i class="fa fa-dashboard"></i> ${window.gettext('Dashboard')}
          </a>
      </div>
      <hr>
      <div class="profile-menu">
          <a href="${basePath}${orderPath}" target="_self" class="btn btn-outline-success">
              <i class="fa fa-shopping-cart"></i> ${window.gettext('My orders')}
          </a>
      </div>
      <div class="profile-menu">
          <a href="${basePath}${ticketPath}" target="_self" class="btn btn-outline-success">
              <i class="fa fa-ticket"></i> ${window.gettext('My tickets')}
          </a>
      </div>`
  ];

  if (talksPublished && hasCfpSubmissions) {
    blocks.push(
      `<hr>
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
              <i class="fa fa-envelope"></i> ${window.gettext('Speaker Emails')}
          </a>
      </div>`
    );
  }

  blocks.push(
    `<hr>
      <div class="profile-menu">
        <a href="${basePath}${profilePath}" target="_self" class="btn btn-outline-success">
        <i class="fa fa-user"></i> ${window.gettext('Account')}
        </a>
      </div>`
  );

  if (showOrganizerArea) {
    blocks.push(
      `<div class="profile-menu organizer-area">
          <a href="${basePath}/common/event/${organizerName}/${eventSlug}" target="_self" class="btn btn-outline-success">
              <i class="fa fa-gears"></i> ${window.gettext('Organizer area')}
          </a>
      </div>`
    );
  }

  blocks.push(
    `<div class="profile-menu">
        <a href="${basePath}${logoutPath}" target="_self" class="btn btn-outline-success">
            <i class="fa fa-sign-out"></i> ${window.gettext('Logout')}
        </a>
    </div>
    </div>`
  );

  const options = {
    html: true,
    content: blocks.join('\n'),
    placement: 'bottom',
    trigger: 'manual'
  };

  $('[data-toggle="popover-profile"]').popover(options).click(function (evt) {
    evt.stopPropagation();
    togglePopover(this);

    $(this).one('shown.bs.popover', function () {
      handleProfileMenuClick();
    });
  })
})

$('html').click(function () {
  $('[data-toggle="popover"]').popover('hide');
  $('[data-toggle="popover-profile"]').popover('hide');
});
