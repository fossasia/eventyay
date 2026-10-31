<script>
import { h as createElement, Comment } from 'vue'
export default {
	props: {
		columnMinWidth: {
			type: Number,
			default: 360
		}
	},
	data() {
		return {
			width: 0
		}
	},
	mounted() {
		this.updateWidth()
		this.observer = new ResizeObserver(entries => {
			for (const entry of entries) {
				if (entry.contentRect && entry.contentRect.width) {
					this.width = Math.round(entry.contentRect.width)
				}
			}
		})
		this.observer.observe(this.$el)
		window.addEventListener('resize', this.updateWidth, { passive: true })
	},
	beforeUnmount() {
		if (this.observer) this.observer.disconnect()
		window.removeEventListener('resize', this.updateWidth)
	},
	methods: {
		updateWidth() {
			if (this.$el) {
				this.width = Math.round(this.$el.clientWidth || this.$el.getBoundingClientRect().width)
			}
		}
	},
	render() {
		// filter out v-if=false nodes
		const panels = this.$slots.default ? this.$slots.default().filter(vnode => vnode.type !== Comment) : []
		const panelCount = panels.length
		if (panelCount === 0) {
			return createElement('div', { class: 'c-dashboard-layout' }, [])
		}
		let columnCount = panelCount > 1 ? Math.min(panelCount, 3) : 1
		if (this.width > 0) {
			const maxColumnCount = Math.floor(this.width / this.columnMinWidth)
			columnCount = Math.max(1, Math.min(maxColumnCount, panelCount))
		}
		const columns = []
		if (columnCount > 1) {
			const firstItem = panels.shift()
			const firstColumnClasses = ['column']
			if (firstItem?.props?.class) {
				firstColumnClasses.push(firstItem.props.class)
			}
			columns.push(createElement('div', {
				class: firstColumnClasses.join(' ')
			}, [firstItem]))

			const remainingColumns = columnCount - 1
			for (let c = 0; c < remainingColumns; c++) {
				const columnItems = []
				const panelsToTake = Math.ceil(panels.length / (remainingColumns - c))
				for (let p = 0; p < panelsToTake; p++) {
					columnItems.push(panels.shift())
				}
				const columnClasses = ['column']
				for (const item of columnItems) {
					if (item?.props?.class) {
						columnClasses.push(item.props.class)
					}
				}
				columns.push(createElement('div', {
					class: columnClasses.join(' ')
				}, columnItems))
			}
		} else {
			const columnClasses = ['column']
			for (const item of panels) {
				if (item?.props?.class) {
					columnClasses.push(item.props.class)
				}
			}
			columns.push(createElement('div', {
				class: columnClasses.join(' ')
			}, panels))
		}
		return createElement('div', {
			class: 'c-dashboard-layout'
		}, columns)
	}
}
</script>
<style lang="stylus">
.c-dashboard-layout
	flex: auto
	display: flex
	min-height: 0
	min-width: 0
	max-width: 100%
	> .column
		flex: 1 1 0px
		display: flex
		flex-direction: column
		min-height: 0
		min-width: 0
		&:not(:last-child)
			border-right: border-separator()
</style>
