const BASE_PATH_ID='base_path';const ORGANIZER_NAME_ID='organizer_name';const EVENT_SLUG_ID='event_slug';const SHOW_ORGANIZER_AREA_ID='show_organizer_area';$(function(){const basePathDefinition=document.getElementById(BASE_PATH_ID);const orgNameDefinition=document.getElementById(ORGANIZER_NAME_ID);const eventSlugDefinition=document.getElementById(EVENT_SLUG_ID);const showOrganizerAreaDefinition=document.getElementById(SHOW_ORGANIZER_AREA_ID);let basePath='';if(basePathDefinition){basePath=JSON.parse(basePathDefinition.textContent);}else{console.error(`JSON element to define ${BASE_PATH_ID} is missing!`)
return;}
let organizerName='';if(orgNameDefinition){organizerName=JSON.parse(orgNameDefinition.textContent);}else{console.warn(`JSON element to define ${ORGANIZER_NAME_ID} is missing!`)}
let eventSlug='';if(eventSlugDefinition){eventSlug=JSON.parse(eventSlugDefinition.textContent);}else{console.warn(`JSON element to define ${EVENT_SLUG_ID} is missing!`)}
let showOrganizerArea=false;if(showOrganizerAreaDefinition){showOrganizerArea=JSON.parse(showOrganizerAreaDefinition.textContent);}else{console.warn(`JSON element to define ${SHOW_ORGANIZER_AREA_ID} is missing!`)}
const options={html:true,content:`
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
      </div>`,placement:'bottom',trigger:'manual'}
$('[data-toggle="popover"]').popover(options).click(function(evt){evt.stopPropagation();$(this).popover('show');$('[data-toggle="popover-profile"]').popover('hide');});})
$(function(){const basePathDefinition=document.getElementById(BASE_PATH_ID);const orgNameDefinition=document.getElementById(ORGANIZER_NAME_ID);const eventSlugDefinition=document.getElementById(EVENT_SLUG_ID);const showOrganizerAreaDefinition=document.getElementById(SHOW_ORGANIZER_AREA_ID);let basePath='';if(basePathDefinition){basePath=JSON.parse(basePathDefinition.textContent);}else{console.error(`JSON element to define ${BASE_PATH_ID} is missing!`)
return;}
let organizerName='';if(orgNameDefinition){organizerName=JSON.parse(orgNameDefinition.textContent);}else{console.warn(`JSON element to define ${ORGANIZER_NAME_ID} is missing!`)}
let eventSlug='';if(eventSlugDefinition){eventSlug=JSON.parse(eventSlugDefinition.textContent);}else{console.warn(`JSON element to define ${EVENT_SLUG_ID} is missing!`)}
let showOrganizerArea=false;if(showOrganizerAreaDefinition){showOrganizerArea=JSON.parse(showOrganizerAreaDefinition.textContent);}else{console.warn(`JSON element to define ${SHOW_ORGANIZER_AREA_ID} is missing!`)}
const currentPath=window.location.pathname;const queryString=window.location.search;const backUrl=`${currentPath}${queryString}`;const logoutParams=new URLSearchParams({back:backUrl});const logoutPath=`/common/logout/?${logoutParams}`;const profilePath='/common/account/';const orderPath='/common/orders/';const blocks=[`<div data-name="popover-profile-menu">
      <div class="profile-menu">
          <a href="${basePath}${orderPath}" target="_self" class="btn btn-outline-success">
              <i class="fa fa-shopping-cart"></i> ${window.gettext('My orders')}
          </a>
      </div>
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
              <i class="fa fa-envelope"></i> ${window.gettext('Event emails')}
          </a>
      </div>
      <div class="profile-menu">
        <a href="${basePath}${profilePath}" target="_self" class="btn btn-outline-success">
        <i class="fa fa-user"></i> ${window.gettext('Account')}
        </a>
      </div>`,];if(showOrganizerArea){blocks.push(`<div class="profile-menu organizer-area">
          <a href="${basePath}/common/event/${organizerName}/${eventSlug}" target="_self" class="btn btn-outline-success">
              <i class="fa fa-gears"></i> ${window.gettext('Organizer area')}
          </a>
      </div>`);}
blocks.push(`<div class="profile-menu">
        <a href="${basePath}${logoutPath}" target="_self" class="btn btn-outline-success">
            <i class="fa fa-sign-out"></i> ${window.gettext('Logout')}
        </a>
    </div>`);const options={html:true,content:blocks.join('\n'),placement:'bottom',trigger:'manual'};$('[data-toggle="popover-profile"]').popover(options).click(function(evt){evt.stopPropagation();togglePopover(this);$(this).one('shown.bs.popover',function(){handleProfileMenuClick();});})})
$('html').click(function(){$('[data-toggle="popover"]').popover('hide');$('[data-toggle="popover-profile"]').popover('hide');});;function togglePopover(element){const popover=$(element).data('bs.popover');const isVisible=popover.tip().hasClass('in');$('[data-toggle="popover"]').popover('hide');if(isVisible){$(element).popover('hide');}else{$(element).popover('show');}}
function handleProfileMenuClick(){$('.profile-menu').off('click').on('click',function(event){event.preventDefault();const link=$(this).find('a');if(link.length>0){window.location.href=link.attr('href');}});$('.submenu-item').off('click').on('click',function(event){event.preventDefault();const link=$(this).find('a');if(link.length>0){window.location.href=link.attr('href');}});$('.dashboard-item').off('click.desktop').on('click.desktop',function(event){if(window.innerWidth>992){event.preventDefault();event.stopPropagation();$('.dashboard-item').not(this).removeClass('desktop-menu-open desktop-submenu-open');$(this).toggleClass('desktop-menu-open desktop-submenu-open');}});let desktopDismissalStep=0;let desktopDismissalTimer=null;$(document).off('click.desktop-submenu').on('click.desktop-submenu',function(event){if(window.innerWidth>992){const $target=$(event.target);const $closestDashboard=$target.closest('.dashboard-item');const $closestSubmenu=$target.closest('#submenu');const $closestPopover=$target.closest('[data-name="popover-profile-menu"]');if($closestSubmenu.length||$closestDashboard.length){return;}
if($closestPopover.length){const hasOpenSubmenu=$('.dashboard-item.desktop-submenu-open').length>0;if(hasOpenSubmenu&&desktopDismissalStep===0){$('.dashboard-item').removeClass('desktop-submenu-open');desktopDismissalStep=1;clearTimeout(desktopDismissalTimer);desktopDismissalTimer=setTimeout(()=>{desktopDismissalStep=0;},3000);return;}else if(desktopDismissalStep===1){$('.dashboard-item').removeClass('desktop-menu-open');$('[data-toggle="popover-profile"]').popover('hide');desktopDismissalStep=0;clearTimeout(desktopDismissalTimer);return;}else if(!hasOpenSubmenu){$('.dashboard-item').removeClass('desktop-menu-open');$('[data-toggle="popover-profile"]').popover('hide');desktopDismissalStep=0;clearTimeout(desktopDismissalTimer);return;}}else{$('.dashboard-item').removeClass('desktop-menu-open desktop-submenu-open');$('[data-toggle="popover-profile"]').popover('hide');desktopDismissalStep=0;clearTimeout(desktopDismissalTimer);}}});$(document).off('keydown.desktop-submenu').on('keydown.desktop-submenu',function(event){if(event.key==='Escape'&&window.innerWidth>992){if($('.dashboard-item.desktop-submenu-open').length>0){$('.dashboard-item').removeClass('desktop-submenu-open');desktopDismissalStep=1;clearTimeout(desktopDismissalTimer);desktopDismissalTimer=setTimeout(()=>{desktopDismissalStep=0;},3000);}else{$('.dashboard-item').removeClass('desktop-menu-open');$('[data-toggle="popover-profile"]').popover('hide');desktopDismissalStep=0;clearTimeout(desktopDismissalTimer);}}});$(document).off('click.desktop-submenu-content').on('click.desktop-submenu-content','#submenu',function(event){if(window.innerWidth>992){event.stopPropagation();}});$('.dashboard-item').off('click.dashboard').on('click.dashboard',function(event){if(window.innerWidth<=992){event.preventDefault();event.stopPropagation();$('.dashboard-item').not(this).removeClass('menu-open');$(this).toggleClass('menu-open');const $this=$(this);const $submenu=$this.find('#submenu');if($this.hasClass('menu-open')){$this.css('position','relative');$submenu.addClass('show');setTimeout(()=>{if($submenu.length&&$submenu[0]){const submenuRect=$submenu[0].getBoundingClientRect();const viewportWidth=window.innerWidth;const viewportHeight=window.innerHeight;if(submenuRect.right>viewportWidth-10){$submenu.css({'left':'auto','right':'0'});}
if(submenuRect.bottom>viewportHeight-10){$submenu.css({'top':'auto','bottom':'100%'});}}},50);}else{$submenu.removeClass('show');}}});let dismissalStep=0;let dismissalTimer=null;$(document).off('click.submenu').on('click.submenu',function(event){if(window.innerWidth<=992){const $target=$(event.target);const $closestDashboard=$target.closest('.dashboard-item');const $closestSubmenu=$target.closest('#submenu');const $closestPopover=$target.closest('[data-name="popover-profile-menu"]');if($closestSubmenu.length||$closestDashboard.length){return;}
if($closestPopover.length){const hasOpenSubmenu=$('.dashboard-item.menu-open').length>0;if(hasOpenSubmenu&&dismissalStep===0){$('.dashboard-item').removeClass('menu-open');$('.dashboard-item #submenu').removeClass('show');dismissalStep=1;clearTimeout(dismissalTimer);dismissalTimer=setTimeout(()=>{dismissalStep=0;},3000);return;}else if(dismissalStep===1){$('[data-toggle="popover-profile"]').popover('hide');dismissalStep=0;clearTimeout(dismissalTimer);return;}else if(!hasOpenSubmenu){$('[data-toggle="popover-profile"]').popover('hide');dismissalStep=0;clearTimeout(dismissalTimer);return;}}else{$('.dashboard-item').removeClass('menu-open');$('.dashboard-item #submenu').removeClass('show');$('[data-toggle="popover-profile"]').popover('hide');dismissalStep=0;clearTimeout(dismissalTimer);}}});$(document).off('click.submenu-content').on('click.submenu-content','#submenu',function(event){if(window.innerWidth<=992){event.stopPropagation();}});$(document).off('keydown.submenu').on('keydown.submenu',function(event){if(event.key==='Escape'&&window.innerWidth<=992){if($('.dashboard-item.menu-open').length>0){$('.dashboard-item').removeClass('menu-open');$('.dashboard-item #submenu').removeClass('show');dismissalStep=1;clearTimeout(dismissalTimer);dismissalTimer=setTimeout(()=>{dismissalStep=0;},3000);}else{$('[data-toggle="popover-profile"]').popover('hide');dismissalStep=0;clearTimeout(dismissalTimer);}}});$('[data-toggle="popover-profile"]').on('hidden.bs.popover',function(){dismissalStep=0;desktopDismissalStep=0;clearTimeout(dismissalTimer);clearTimeout(desktopDismissalTimer);$('.dashboard-item').removeClass('menu-open desktop-menu-open desktop-submenu-open');$('.dashboard-item #submenu').removeClass('show');});}
$(document).ready(function(){handleProfileMenuClick();});;