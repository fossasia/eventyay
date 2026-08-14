export function isRoomTypeAvailable(typeId, hasPermission, isAdminMode = false) {
	if (typeId === 'stage') {
		return hasPermission('world:rooms.create.stage')
	}
	if (typeId === 'channel-bbb' || typeId === 'channel-janus' || typeId === 'channel-zoom') {
		return hasPermission('world:rooms.create.bbb')
	}
	if (typeId === 'channel-jitsi') {
		return isAdminMode && hasPermission('world:rooms.create.jitsi')
	}
	if (typeId === 'channel-text') {
		return hasPermission('world:rooms.create.chat')
	}
	if (typeId === 'exhibition') {
		return hasPermission('world:rooms.create.exhibition')
	}
	if (typeId === 'posters') {
		return hasPermission('world:rooms.create.poster')
	}
	if (typeId === 'channel-roulette' || 
		typeId === 'page-static' || 
		typeId === 'page-iframe' || 
		typeId === 'page-landing' || 
		typeId === 'page-userlist') {
		return hasPermission('room:update')
	}
	return true
}

export function filterRoomTypesByPermission(roomTypes, hasPermission, isAdminMode = false) {
	return roomTypes.filter(type => isRoomTypeAvailable(type.id, hasPermission, isAdminMode))
}
