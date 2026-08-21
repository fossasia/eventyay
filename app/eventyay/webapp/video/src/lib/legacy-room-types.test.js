/**
 * Legacy video room types are kept for existing events but cannot be created.
 * Run: node --test src/lib/legacy-room-types.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import {
	LEGACY_ROOM_TYPE_IDS,
	UNSUPPORTED_CREATE_MODULE_TYPES,
	filterCreatableRoomTypes,
	isLegacyRoomTypeId,
	isUnsupportedCreateModuleType,
} from './legacy-room-types.js'

test('legacy room type ids match the removed create-room options', () => {
	assert.deepEqual([...LEGACY_ROOM_TYPE_IDS], [
		'exhibition',
		'page-static',
		'page-iframe',
		'page-userlist',
	])
})

test('legacy module types match the removed create-room options', () => {
	assert.deepEqual([...UNSUPPORTED_CREATE_MODULE_TYPES], [
		'exhibition.native',
		'page.static',
		'page.iframe',
		'page.userlist',
	])
})

test('isLegacyRoomTypeId identifies only removed create-room types', () => {
	assert.equal(isLegacyRoomTypeId('exhibition'), true)
	assert.equal(isLegacyRoomTypeId('page-static'), true)
	assert.equal(isLegacyRoomTypeId('page-iframe'), true)
	assert.equal(isLegacyRoomTypeId('page-userlist'), true)
	assert.equal(isLegacyRoomTypeId('stage'), false)
	assert.equal(isLegacyRoomTypeId('channel-text'), false)
	assert.equal(isLegacyRoomTypeId('channel-bbb'), false)
})

test('isUnsupportedCreateModuleType identifies only removed create-room modules', () => {
	assert.equal(isUnsupportedCreateModuleType('exhibition.native'), true)
	assert.equal(isUnsupportedCreateModuleType('page.static'), true)
	assert.equal(isUnsupportedCreateModuleType('livestream.native'), false)
	assert.equal(isUnsupportedCreateModuleType('chat.native'), false)
	assert.equal(isUnsupportedCreateModuleType('call.bigbluebutton'), false)
})

test('filterCreatableRoomTypes removes legacy types and keeps supported ones', () => {
	const filtered = filterCreatableRoomTypes([
		{id: 'stage'},
		{id: 'channel-bbb'},
		{id: 'channel-text'},
		{id: 'exhibition'},
		{id: 'page-static'},
		{id: 'page-iframe'},
		{id: 'page-userlist'},
		{id: 'posters'},
	])
	assert.deepEqual(filtered.map(type => type.id), [
		'stage',
		'channel-bbb',
		'channel-text',
		'posters',
	])
})
