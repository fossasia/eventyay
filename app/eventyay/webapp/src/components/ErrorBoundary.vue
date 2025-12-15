<template>
	<div>
		<div v-if="errored" class="c-error-boundary">
			<div class="c-error-boundary__content">
				<div class="mdi mdi-alert-octagon c-error-boundary__icon"></div>
				<h2>{{ title }}</h2>
				<p class="c-error-boundary__message">{{ errorMessage }}</p>
				<div class="c-error-boundary__actions">
					<button class="bunt-button" @click="reload">{{ $t ? $t('ErrorBoundary:reload') : 'Reload' }}</button>
					<button class="bunt-button" v-if="showDetails" @click="toggleDetails">{{ detailsVisible ? ($t ? $t('ErrorBoundary:hide_details') : 'Hide details') : ($t ? $t('ErrorBoundary:show_details') : 'Show details') }}</button>
				</div>
				<pre v-if="detailsVisible" class="c-error-boundary__stack">{{ stack }}</pre>
			</div>
		</div>
		<slot v-else />
	</div>
</template>

<script>
import reportError from 'lib/errorReporter'

export default {
	name: 'ErrorBoundary',
	props: {
		title: { type: String, default: 'An error occurred' },
		showDetails: { type: Boolean, default: true }
	},
	data() {
		return {
			errored: false,
			error: null,
			info: null,
			detailsVisible: false
		}
	},
	computed: {
		errorMessage() {
			return this.error?.message || (this.info || '')
		},
		stack() {
			return this.error?.stack || ''
		}
	},
	methods: {
		reload() {
			window.location.reload()
		},
		toggleDetails() {
			this.detailsVisible = !this.detailsVisible
		}
	},
	errorCaptured(err, vm, info) {
		// mark as errored and capture info
		this.errored = true
		this.error = err
		this.info = info
		try {
			reportError(err, { info })
		} catch (e) {
			// never throw from error boundary
			/* noop */
		}
		// return false to stop the error from propagating to parent handlers
		return false
	}
}
</script>

<style scoped>
.c-error-boundary {
	position: fixed;
	top: 48px;
	left: 0;
	right: 0;
	bottom: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 3000;
	background: rgba(255,255,255,0.95);
}
.c-error-boundary__content {
	max-width: 800px;
	padding: 24px;
	text-align: center;
}
.c-error-boundary__icon { font-size: 48px; color: var(--clr-danger); }
.c-error-boundary__message { margin-top: 12px; color: var(--clr-text-secondary); }
.c-error-boundary__stack { text-align:left; max-height: 300px; overflow:auto; background:#f6f8fa; padding:12px; margin-top:12px }
</style>
