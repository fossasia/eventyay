/**
 * Run: node --test src/lib/room-type-permissions.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { filterRoomTypesByPermission, isRoomTypeAvailable } from './room-type-permissions.js'

const allow = (...granted) => permission => granted.includes(permission)
const allowAll = () => true

test('supported room types stay available with the matching permission', () => {
	assert.equal(isRoomTypeAvailable('stage', allow('world:rooms.create.stage')), true)
	assert.equal(isRoomTypeAvailable('channel-bbb', allow('world:rooms.create.bbb')), true)
	assert.equal(isRoomTypeAvailable('channel-text', allow('world:rooms.create.chat')), true)
	assert.equal(isRoomTypeAvailable('channel-jitsi', allow('world:rooms.create.jitsi'), true), true)
	assert.equal(isRoomTypeAvailable('channel-jitsi', allow('world:rooms.create.jitsi'), false), false)
})

test('filterRoomTypesByPermission keeps only types the user can create', () => {
	const filtered = filterRoomTypesByPermission([
		{id: 'stage'},
		{id: 'channel-bbb'},
		{id: 'channel-text'},
	], allow('world:rooms.create.stage', 'world:rooms.create.chat'), false)
	assert.deepEqual(filtered.map(type => type.id), [
		'stage',
		'channel-text',
	])
})

test('filterRoomTypesByPermission with all permissions keeps the remaining types', () => {
	const filtered = filterRoomTypesByPermission([
		{id: 'stage'},
		{id: 'channel-bbb'},
		{id: 'channel-text'},
		{id: 'posters'},
		{id: 'page-landing'},
	], allowAll, true)
	assert.deepEqual(filtered.map(type => type.id), [
		'stage',
		'channel-bbb',
		'channel-text',
		'posters',
		'page-landing',
	])
})
