export function isRoomTypeAvailable(typeId, hasPermission, isAdminMode = false, isBbbAvailable = true) {
	if (typeId === 'stage') {
		return hasPermission('world:rooms.create.stage')
	}
	if (typeId === 'channel-bbb') {
		if (!isBbbAvailable) return false
		return isAdminMode && hasPermission('world:rooms.create.bbb')
	}
	if (typeId === 'channel-janus' || typeId === 'channel-zoom') {
		return isAdminMode && hasPermission('world:rooms.create.bbb')
	}
	if (typeId === 'channel-jitsi') {
		return isAdminMode && hasPermission('world:rooms.create.jitsi')
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

export function filterRoomTypesByPermission(roomTypes, hasPermission, isAdminMode = false, isBbbAvailable = true) {
	return roomTypes.filter(type => isRoomTypeAvailable(type.id, hasPermission, isAdminMode, isBbbAvailable))
}
