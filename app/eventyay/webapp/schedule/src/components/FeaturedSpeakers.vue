<template lang="pug">
.c-featured-speakers
	speakers-list(:featured-only="true", :hide-toolbar="true", view-mode="details")
</template>

<script>
import SpeakersList from './SpeakersList.vue'

export default {
	name: 'FeaturedSpeakers',
	components: { SpeakersList },
}
</script>

<style lang="stylus">
.c-featured-speakers
	min-height: 0
</style>
