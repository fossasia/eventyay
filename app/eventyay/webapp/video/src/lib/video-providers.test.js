/**
 * Video provider dropdown helpers.
 * Run: node --test src/lib/video-providers.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import {
	VIDEO_CREATE_PROVIDERS,
	applyVideoProviderToConfig,
	getAvailableVideoProviders,
	getConfiguredRoomLabel,
	isVideoProviderEnabled,
	isVideoProviderPermitted,
} from './video-providers.js'

function allow(permissions) {
	const permitted = new Set(permissions)
	return (permission) => permitted.has(permission)
}

function features(enabledFlags) {
	const flags = new Set(enabledFlags)
	return (flag) => flags.has(flag)
}

test('dropdown labels match the organiser create options', () => {
	assert.deepEqual(
		VIDEO_CREATE_PROVIDERS.map(provider => provider.label),
		['Stream (YT, HLS)', 'BBB', 'Jitsi', 'Janus']
	)
})

test('disabled feature flags hide Jitsi and Janus', () => {
	const providers = getAvailableVideoProviders(
		allow(['room:update']),
		false,
		features([])
	)
	assert.deepEqual(providers.map(provider => provider.id), ['stream', 'bbb'])
})

test('enabled Jitsi and Janus flags include those providers', () => {
	const providers = getAvailableVideoProviders(
		allow(['room:update']),
		false,
		features(['jitsi', 'janus'])
	)
	assert.deepEqual(providers.map(provider => provider.id), ['stream', 'bbb', 'jitsi', 'janus'])
})

test('users without create or update permission see no providers', () => {
	const providers = getAvailableVideoProviders(
		allow([]),
		false,
		features(['jitsi', 'janus'])
	)
	assert.equal(providers.length, 0)
})

test('stage create permission is enough for Stream', () => {
	const providers = getAvailableVideoProviders(
		allow(['world:rooms.create.stage']),
		false,
		features([])
	)
	assert.deepEqual(providers.map(provider => provider.id), ['stream'])
})

test('Jitsi does not require admin mode when the organiser can update rooms', () => {
	assert.equal(
		isVideoProviderPermitted(
			VIDEO_CREATE_PROVIDERS.find(provider => provider.id === 'jitsi'),
			allow(['room:update']),
			false
		),
		true
	)
})

test('Jitsi stays hidden when its feature flag is off', () => {
	assert.equal(
		isVideoProviderEnabled(
			VIDEO_CREATE_PROVIDERS.find(provider => provider.id === 'jitsi'),
			features([])
		),
		false
	)
})

test('configured room labels include the video provider', () => {
	assert.equal(getConfiguredRoomLabel({id: 'stage', name: 'Stage'}), 'Stage: Stream')
	assert.equal(getConfiguredRoomLabel({id: 'channel-bbb', name: 'Video Channel'}), 'Video Channel: BBB')
	assert.equal(getConfiguredRoomLabel({id: 'channel-jitsi', name: 'Video Channel (Jitsi)'}), 'Video Channel: Jitsi')
	assert.equal(getConfiguredRoomLabel({id: 'channel-janus', name: 'Video Channel (beta)'}), 'Video Channel: Janus')
	assert.equal(getConfiguredRoomLabel({id: 'channel-zoom', name: 'Video Channel (Zoom)'}), 'Video Channel: Zoom')
	assert.equal(getConfiguredRoomLabel({id: 'channel-text', name: 'Text Channel'}), 'Text Channel')
})

test('applying a provider sets the starting module config', () => {
	const config = { module_config: [] }
	assert.equal(
		applyVideoProviderToConfig(config, {id: 'stage', startingModule: 'livestream.native'}),
		true
	)
	assert.deepEqual(config.module_config, [{
		type: 'livestream.native',
		config: { playback_mode: 'always_on' }
	}])
})
