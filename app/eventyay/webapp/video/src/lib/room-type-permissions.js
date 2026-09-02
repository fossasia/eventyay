export function isRoomTypeAvailable(typeId, hasPermission, isAdminMode = false) {
	if (typeId === 'stage') {
		return hasPermission('world:rooms.create.stage') || hasPermission('room:update')
	}
	if (typeId === 'channel-bbb' || typeId === 'channel-janus' || typeId === 'channel-zoom') {
		return hasPermission('world:rooms.create.bbb') || hasPermission('room:update')
	}
	if (typeId === 'channel-jitsi') {
		return hasPermission('world:rooms.create.jitsi') || hasPermission('room:update')
	}
	if (typeId === 'channel-text') {
		return hasPermission('world:rooms.create.chat')
	}
	if (typeId === 'channel-roulette') {
		return isAdminMode && hasPermission('room:update')
	}
	if (typeId === 'page-landing') {
		return hasPermission('room:update')
	}
	return true
}

export function filterRoomTypesByPermission(roomTypes, hasPermission, isAdminMode = false) {
	return roomTypes.filter(type => isRoomTypeAvailable(type.id, hasPermission, isAdminMode))
}
