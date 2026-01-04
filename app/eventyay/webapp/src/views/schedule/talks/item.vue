<template lang="pug">
SessionDetail(:talkId="talkId" context="talk")
</template>
<script>
// Using standard script for compatibility if setup not fully adopted in routing/views yet, though setup is fine.
import SessionDetail from 'modules/sessions/components/SessionDetail.vue'

export default {
	components: { SessionDetail },
	props: {
		talkId: String
	}
}
</script>

