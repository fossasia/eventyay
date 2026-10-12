/**
 * Checks for the shift claim/drop email choice helpers.
 * Run: node --test src/teamshifts-adapter/index.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { getShiftActionEmails, roleActionApplied, roleActionPayload, scheduleApiUrl, setShiftActionEmails } from './index.js'

test('the email choice defaults to on when the backend sends none', () => {
	assert.equal(getShiftActionEmails(null), true)
	assert.equal(getShiftActionEmails({ schedule: {} }), true)
})

test('the saved email choice is read from the schedule payload', () => {
	assert.equal(getShiftActionEmails({ schedule: { shift_action_emails: false } }), false)
	assert.equal(getShiftActionEmails({ shift_action_emails: false }), false)
	assert.equal(getShiftActionEmails({ value: { schedule: { shift_action_emails: false } } }), false)
})

test('the request body carries the role and the send_email choice', () => {
	assert.deepEqual(roleActionPayload({ id: 7 }, true), { role_id: 7, send_email: true })
	assert.deepEqual(roleActionPayload({ id: 7 }, false), { role_id: 7, send_email: false })
})

test('a saved response choice pre-fills the next dialog', () => {
	const scheduleData = { schedule: { shift_action_emails: true } }
	setShiftActionEmails(scheduleData, false)
	assert.equal(getShiftActionEmails(scheduleData), false)
	assert.deepEqual(roleActionPayload({ id: 3 }, getShiftActionEmails(scheduleData)), { role_id: 3, send_email: false })

	setShiftActionEmails(scheduleData, true)
	assert.equal(getShiftActionEmails(scheduleData), true)
})

test('updating the choice works when the schedule data is a ref', () => {
	const scheduleData = { value: { schedule: { shift_action_emails: true } } }
	setShiftActionEmails(scheduleData, false)
	assert.equal(scheduleData.value.schedule.shift_action_emails, false)
})

test('a drop counts as applied once the user is no longer on the role', () => {
	const roles = [{ id: 4, assigned: [{ id: 9, name: 'Other' }] }]
	assert.equal(roleActionApplied('drop', roles, 4, 7), true)
	assert.equal(roleActionApplied('drop', [{ id: 4, assigned: [{ id: 7, name: 'Me' }] }], 4, 7), false)
})

test('a claim counts as applied once the user is on the role', () => {
	assert.equal(roleActionApplied('claim', [{ id: 4, assigned: [{ id: 7, name: 'Me' }] }], 4, 7), true)
	assert.equal(roleActionApplied('claim', [{ id: 4, assigned: [] }], 4, 7), false)
	assert.equal(roleActionApplied('claim', [], 4, 7), false)
})

test('the schedule API URL is built from the event URL', () => {
	assert.equal(scheduleApiUrl('/org/event'), '/org/event/teamshifts/shifts/api/')
	assert.equal(scheduleApiUrl('/org/event/'), '/org/event/teamshifts/shifts/api/')
})
