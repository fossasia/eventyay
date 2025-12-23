<template lang="pug">
.c-room-edit-form
	.scroll-wrapper(v-scrollbar.y="")
		.ui-form-body
			.generic-settings
				bunt-input(name="name", v-model="localizedName", label="Name", :validation="v$.config.name")
				bunt-input(name="description", v-model="localizedDescription", label="Description")
				bunt-input(name="sorting_priority", v-model="config.sorting_priority", label="Sorting priority", :validation="v$.config.sorting_priority")
				template(v-if="inferredType")
					bunt-input(v-if="inferredType.id === 'stage' || inferredType.id === 'channel-bbb'", name="pretalx_id", v-model="config.pretalx_id", label="pretalx ID", :validation="v$.config.pretalx_id")
					bunt-checkbox(v-if="inferredType.id === 'channel-text'", name="force_join", v-model="config.force_join", label="Force join on login (use for non-volatile, text-based chats only!!)")
		async save() {
			this.error = null
			this.v$.$touch()
			if (this.v$.$invalid) return
			this.$refs.settings?.beforeSave?.()
			this.saving = true
			try {
				let roomId = this.config.id
				if (this.creating) {
					({ room: roomId } = await this.$store.dispatch('createRoom', {
						name: this.config.name,
						description: this.config.description,
						modules: []
					}))
				}
				const module_config = Array.isArray(this.config.module_config) ? this.config.module_config : []
				const setup_complete = module_config.length > 0
				let sidebar_hidden
				if (setup_complete && !this.config.setup_complete) {
					// Setup just completed, show in sidebar
					sidebar_hidden = false
				} else if (setup_complete) {
					// Setup was already complete, preserve user preference
					sidebar_hidden = this.config.sidebar_hidden
				} else {
					// Setup incomplete, hide from sidebar
					sidebar_hidden = true
				}
				const roomData = {
				await api.call('room.config.patch', {
					room: roomId,
					name: this.config.name,
					description: this.config.description,
					sorting_priority: this.config.sorting_priority === '' ? undefined : this.config.sorting_priority,
					pretalx_id: this.config.pretalx_id || 0, // TODO weird default
					picture: this.config.picture,
					force_join: this.config.force_join,
					hidden: !!this.config.hidden,
					sidebar_hidden: !!this.config.sidebar_hidden,
					module_config: this.config.module_config,
				})
					sidebar_hidden,
					setup_complete,
					module_config,
				}
				const updatedConfig = await api.call('room.config.patch', roomData)
				Object.assign(this.config, updatedConfig)
					module_config: this.config.module_config,
				})
				this.saving = false
				if (this.creating) {
					this.$router.push({name: 'admin:rooms:item', params: {roomId}})
				}
			} catch (error) {
				console.error(error)
				this.saving = false
				this.error = error.message || error
			}
		}
	}
}
</script>
<style lang="stylus">
.c-room-edit-form
	flex: auto
	min-height: 0
	height: 100vh
	display: flex
	flex-direction: column
	.scroll-wrapper
		flex: auto
		min-height: 0
		display: flex
		flex-direction: column
</style>
