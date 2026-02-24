<template>
  <App />
</template>

<script>
import App from './app.vue'

export default {
  name: 'WebCheckinRoot',
  components: { App },
  props: {
    rootData: {
      type: Object,
      required: true,
    },
  },
  data() {
    // Detach from the prop object to avoid Vue warnings about prop mutation.
    return { ...this.rootData }
  },
}
</script>
