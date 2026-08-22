export function isBbbConfigured(world) {
	return world?.bbb_available === true
}

export function isRoomTypeAvailable(typeId, hasPermission, isAdminMode = false, options = {}) {
	if (typeId === 'stage') {
		return hasPermission('world:rooms.create.stage')
	}
	if (typeId === 'channel-bbb' || typeId === 'channel-janus' || typeId === 'channel-zoom') {
		return hasPermission('world:rooms.create.bbb')
	}
	if (typeId === 'channel-video-chat') {
		return hasPermission('world:rooms.create.bbb') && options.bbbAvailable === true
	}
	if (typeId === 'channel-jitsi') {
		return isAdminMode && hasPermission('world:rooms.create.jitsi')
	}
	if (typeId === 'channel-text') {
		return hasPermission('world:rooms.create.chat')
	}
	if (typeId === 'posters') {
		return hasPermission('world:rooms.create.poster')
	}
	if (typeId === 'channel-roulette' || typeId === 'page-landing') {
		return hasPermission('room:update')
	}
	return true
}

export function filterRoomTypesByPermission(roomTypes, hasPermission, isAdminMode = false, options = {}) {
	return roomTypes.filter(type => isRoomTypeAvailable(type.id, hasPermission, isAdminMode, options))
}
