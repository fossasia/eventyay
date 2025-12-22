<script setup lang="ts">
import { ref, useTemplateRef, onMounted, onBeforeUnmount } from 'vue'

const ENTRY_CLASSES = 'text-[#1a69a4] hover:text-white hover:bg-[#1a69a4] px-4 py-2 block no-underline'
const WITH_ICON_CLASSES = 'flex flex-row items-center space-x-2'
const WITH_BORDER_CLASSES = 'border-t border-s-0 border-e-0 border-b-0 border-solid border-gray-300'
const open = ref(false)
const subOpen = ref(false)
const container = useTemplateRef('container')

function showMenu() {
  open.value = true
}

function closeMenu() {
  open.value = false
}

function handleClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (container.value && !container.value.contains(target)) {
    closeMenu()
  }
}

function handleKeyDown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    closeMenu()
  }
}
function handleLogout(event: Event) {
  event.preventDefault()
  
  // Create and submit a form for logout
  const form = document.createElement('form')
  form.method = 'POST'
  form.action = '/common/logout/'
  
  // Add CSRF token
  const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]') as HTMLInputElement
  if (csrfToken) {
    const csrfInput = document.createElement('input')
    csrfInput.type = 'hidden'
    csrfInput.name = 'csrfmiddlewaretoken'
    csrfInput.value = csrfToken.value
    form.appendChild(csrfInput)
  }
  
  document.body.appendChild(form)
  form.submit()
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeyDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeyDown)
})
</script>

<template>
  <div class='relative font-sans text-sm' ref='container'>
    <button class='text-xl cursor-pointer' @click='showMenu'><i class='fa fa-caret-down'></i></button>
    <div v-if='open' ref='main-menu' class='absolute z-1 end-1 grid grid-cols-1 shadow shadow-lg min-w-48 bg-white'>
      <div class='relative cursor-pointer' @mouseover='subOpen = true' @mouseleave='subOpen = false'>
        <div class='flex flex-row items-center space-x-2' :class='ENTRY_CLASSES' >
          <i class='fa fa-tachometer fa-fw'></i>
          <div class=''>Dashboard</div>
        </div>
        <ul v-if='subOpen' class='absolute z-2 top-0 -translate-x-full list-none m-0 p-s-0 bg-white shadow-lg min-w-56'>
          <li>
            <a href='/common/' :class='[ENTRY_CLASSES, WITH_ICON_CLASSES]' class='block'>
              <i class='fa fa-tachometer fa-fw'></i>
              <div>Main dashboard</div>
            </a>
          </li>
          <li>
            <a href='/control/' :class='[ENTRY_CLASSES, WITH_ICON_CLASSES]' class='block'>
              <i class='fa fa-ticket fa-fw'></i>
              <div>Tickets</div>
            </a>
          </li>
          <li>
            <a href='/orga/event/' :class='[ENTRY_CLASSES, WITH_ICON_CLASSES]' class='block'>
              <i class='fa fa-microphone fa-fw'></i>
              <div>Talks</div>
            </a>
          </li>
        </ul>
      </div>
      <a :class='[ENTRY_CLASSES, WITH_ICON_CLASSES]' href='/common/orders/'>
        <i class='fa fa-shopping-cart fa-fw'></i>
        <div>My orders</div>
      </a>
      <a :class='[ENTRY_CLASSES, WITH_ICON_CLASSES]' href='/common/sessions/'>
        <i class='fa fa-sticky-note-o fa-fw'></i>
        <div>My sessions</div>
      </a>
      <a :class='[ENTRY_CLASSES, WITH_ICON_CLASSES]' href='/common/events/'>
        <i class='fa fa-calendar fa-fw'></i>
        <div>My events</div>
      </a>
      <a :class='[ENTRY_CLASSES, WITH_ICON_CLASSES]' href='/common/organizers/'>
        <i class='fa fa-users fa-fw'></i>
        <div>Organizers</div>
      </a>
      <a :class='[ENTRY_CLASSES, WITH_ICON_CLASSES, WITH_BORDER_CLASSES]' href='/common/account/'>
        <i class='fa fa-user-circle fa-fw'></i>
        <div>Account</div>
      </a>
      <a :class='[ENTRY_CLASSES, WITH_ICON_CLASSES, WITH_BORDER_CLASSES]' href='/admin/'>
        <i class='fa fa-cog fa-fw'></i>
        <div>Admin</div>
      </a>
      <a :class='[ENTRY_CLASSES, WITH_ICON_CLASSES, WITH_BORDER_CLASSES, "w-full text-left"]' @click='handleLogout' href="#">
        <i class='fa fa-sign-out fa-fw'></i>
        <div>Logout</div>
      </a>
    </div>
  </div>
</template>

<style scoped>
/* Menu item icons are visible by default */
.grid .fa:not(.fa-caret-down) {
  color: #1a69a4 !important;
  opacity: 1;
  transition: color 0.2s ease-in-out;
  font-size: 1rem;
  width: 1.25em;
  text-align: center;
}

/* Caret icon should always be visible and inherit color */
.fa-caret-down {
  opacity: 1 !important;
  color: inherit !important;
}

/* Icons turn white when the parent link or div is hovered */
:deep(.hover\:bg-\[\#1a69a4\]:hover) .fa,
.relative:hover .fa {
  color: white !important;
}

/* Ensure icons are white when text turns white on hover */
.fa.fa-fw {
  margin-right: 8px;
}
</style>
