<template>
  <transition name="dropdown-content">
    <div
      v-if="active"
      class="dropdown-content"
    >
      <slot />
    </div>
  </transition>
</template>

<script>
export default {
	name: 'AppDropdownContent',
	inject: ['sharedState'],
	computed: {
		active () {
			return this.sharedState.active
		},
	},
}
</script>

<style>
.dropdown-content {
  position: absolute;
  background: #ffffff;
  margin-top: 4px;
  border: 1px solid rgba(0, 0, 0, 0.38);
  border-radius: 5px;
  max-width: calc(100% - 40px);
  max-height: 350px;
  overflow-y: auto;
}
.dropdown-content .checkbox-line {
  margin: 8px;
}
.dropdown-content .checkbox-line .bunt-checkbox .bunt-checkbox-box {
  min-width: 20px;
}
.dropdown-content-enter-active,
.dropdown-content-leave-active {
  transition: all 0.2s;
}
.dropdown-content-enter,
.dropdown-content-leave-to {
  opacity: 0;
  transform: translateY(-5px);
}

@media screen and (max-width: 480px) {
  .dropdown-content {
    /* left: 5px; */
    max-width: 50%;
    z-index: 10;
  }
}
</style>
