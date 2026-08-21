export const LEGACY_ROOM_TYPE_IDS = Object.freeze([
	'exhibition',
	'page-static',
	'page-iframe',
	'page-userlist',
])

export const UNSUPPORTED_CREATE_MODULE_TYPES = Object.freeze([
	'exhibition.native',
	'page.static',
	'page.iframe',
	'page.userlist',
])

export function isLegacyRoomTypeId(typeId) {
	return LEGACY_ROOM_TYPE_IDS.includes(typeId)
}

export function isUnsupportedCreateModuleType(moduleType) {
	return UNSUPPORTED_CREATE_MODULE_TYPES.includes(moduleType)
}

export function filterCreatableRoomTypes(roomTypes) {
	return roomTypes.filter(type => !isLegacyRoomTypeId(type.id))
}
