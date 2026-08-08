<template lang="pug">
.caption-box(v-if="isVisible")
  .caption-header
    span.status-dot(:class="{ active: isConnected && isBoothActive }")
    span.status-text
      template(v-if="!isConnected") {{ $t('Connecting to live subtitles...') }}
      template(v-else-if="!isBoothActive") {{ $t('Interpreter is offline') }}
      template(v-else) {{ $t('Live Subtitles') }}
  .caption-content
    .caption-line(v-for="caption in captions" :key="caption.id" :class="{ final: caption.is_final }")
      | {{ caption.text }}
</template>

<script>
export default {
  name: 'CaptionBox',
  props: {
    captionUrl: {
      type: String,
      required: true
    },
    listenerToken: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      ws: null,
      isConnected: false,
      isBoothActive: false,
      captions: [],
      maxCaptions: 3,
      isVisible: true
    }
  },
  mounted() {
    this.connect()
  },
  beforeUnmount() {
    this.disconnect()
  },
  methods: {
    connect() {
      if (this.ws) {
        this.ws.close()
      }
      
      const url = new URL(this.captionUrl)
      url.searchParams.set('token', this.listenerToken)
      
      this.ws = new WebSocket(url.toString())
      
      this.ws.onopen = () => {
        this.isConnected = true
      }
      
      this.ws.onclose = () => {
        this.isConnected = false
        this.isBoothActive = false
        // Reconnect after 3 seconds
        setTimeout(() => {
          if (this.captionUrl && this.listenerToken && this._isMounted) {
            this.connect()
          }
        }, 3000)
      }
      
      this.ws.onerror = (error) => {
        console.error('Caption WebSocket error:', error)
      }
      
      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          if (message.type === 'booth:state') {
            this.isBoothActive = message.payload.mic_active && message.payload.ingest_connected
          } else if (message.type === 'caption') {
            this.handleCaption(message.payload)
          }
        } catch (e) {
          console.error('Failed to parse caption message:', e)
        }
      }
    },
    disconnect() {
      if (this.ws) {
        this.ws.close()
        this.ws = null
      }
    },
    handleCaption(payload) {
      // Find existing caption by ID
      const index = this.captions.findIndex(c => c.id === payload.id)
      
      if (index !== -1) {
        // Update existing
        this.captions[index] = payload
      } else {
        // Add new
        this.captions.push(payload)
      }
      
      // Remove old captions if exceeding max
      if (this.captions.length > this.maxCaptions) {
        this.captions = this.captions.slice(this.captions.length - this.maxCaptions)
      }
    }
  },
  watch: {
    captionUrl() {
      this.connect()
    },
    listenerToken() {
      this.connect()
    }
  },
  created() {
    this._isMounted = true
  },
  unmounted() {
    this._isMounted = false
  }
}
</script>

<style lang="stylus" scoped>
.caption-box
  background: var(--b-surface, #fff)
  border: 1px solid var(--b-divider, #eee)
  border-radius: 8px
  padding: 12px
  margin-top: 16px
  box-shadow: 0 4px 6px rgba(0,0,0,0.05)

.caption-header
  display: flex
  align-items: center
  font-size: 12px
  color: var(--b-text-subdued, #666)
  margin-bottom: 8px
  text-transform: uppercase
  letter-spacing: 0.5px

.status-dot
  width: 8px
  height: 8px
  border-radius: 50%
  background-color: var(--b-divider, #ccc)
  margin-right: 8px
  transition: background-color 0.3s ease

  &.active
    background-color: var(--b-success, #4CAF50)
    box-shadow: 0 0 5px var(--b-success, #4CAF50)

.caption-content
  min-height: 24px
  font-size: 16px
  line-height: 1.5
  color: var(--b-text, #333)

.caption-line
  opacity: 0.8
  transition: opacity 0.2s ease
  
  &.final
    opacity: 1.0
</style>
