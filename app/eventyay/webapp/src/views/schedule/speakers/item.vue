<template lang="pug">
SpeakerDetail(:speakerId="speakerId" context="talk")
</template>
<script>
import SpeakerDetail from 'modules/speakers/components/SpeakerDetail.vue'

export default {
	components: { SpeakerDetail },
	props: {
		speakerId: String
	}
}
</script>
