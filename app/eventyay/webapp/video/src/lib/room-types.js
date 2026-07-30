import features from 'features'

const ROOM_TYPES = [{
	id: 'stage',
	icon: 'theater',
	name: 'Stage',
	description: 'A stage allows you to present a live stream to your audience, optionally combined with chat and Q&A features.',
	startingModule: 'livestream.native',
	inferModules: ['livestream.native', 'livestream.youtube', 'livestream.iframe']
}, {
	id: 'channel-bbb',
	icon: 'webcam',
	name: 'Video Channel',
	description: 'A video channel allows you to connect with attendees in real time and host workshops or panels. The video channels are powered by BigBlueButton and support 25-80 people, depending on usage.',
	startingModule: 'call.bigbluebutton',
	videoChannel: true
}, {
	id: 'channel-janus',
	icon: 'webcam',
	name: 'Video Channel (beta)',
	description: 'A video channel allows you to connect with attendees in real time and host workshops or panels. The video channels are powered by Janus.',
	startingModule: 'call.janus',
	videoChannel: true,
	behindFeatureFlag: 'janus'
}, {
	id: 'channel-zoom',
	icon: 'webcam',
	name: 'Video Channel (Zoom)',
	description: 'This room type allows you to embed a zoom meeting or webinar directly into venueless.',
	startingModule: 'call.zoom',
	videoChannel: true,
	behindFeatureFlag: 'zoom'
}, {
	id: 'channel-text',
	icon: 'pound',
	name: 'Text Channel',
	description: 'This type of channel allows you to enable pure-text communication between your attendees.',
	startingModule: 'chat.native'
}, {
	id: 'exhibition',
	icon: 'domain',
	name: 'Exhibition',
	description: 'Using an exhibition room, sponsors or exhibitors can present themselves to your audience.',
	startingModule: 'exhibition.native'
}, {
	id: 'posters',
	icon: 'domain',
	name: 'Poster Hall',
	description: 'Hang your posters high!',
	startingModule: 'poster.native',
	behindFeatureFlag: 'poster'
}, {
	id: 'channel-roulette',
	icon: 'webcam',
	name: 'Random video calls',
	description: 'Connect your attendees for short video calls in random combinations.',
	startingModule: 'networking.roulette',
	inferModules: ['networking.roulette'],
	sidebarGroup: 'networking',
	behindFeatureFlag: 'roulette'
}, {
	id: 'page-static',
	icon: 'text-box-outline',
	name: 'Page',
	description: 'A page contains static content for your attendees.',
	startingModule: 'page.static'
}, {
	id: 'page-iframe',
	icon: 'text-box-outline',
	name: 'IFrame',
	description: 'Using IFrames, you can embed arbitrary web pages and web applications into venueless.',
	startingModule: 'page.iframe'
}, {
	id: 'page-landing',
	icon: 'text-box-outline',
	name: 'Landing Page',
	description: 'The landing place module combines the most important content into one place for your attendees to see after they join.',
	startingModule: 'page.landing',
	behindFeatureFlag: 'page.landing'
}, {
	id: 'page-userlist',
	icon: 'text-box-outline',
	name: 'User List',
	description: '',
	startingModule: 'page.userlist'
}]

export const VIDEO_CHANNEL_MODULE_TYPES = new Set(ROOM_TYPES.filter(type => type.videoChannel).map(type => type.startingModule))
export const NETWORKING_MODULE_TYPES = new Set(ROOM_TYPES.filter(type => type.sidebarGroup === 'networking').map(type => type.startingModule))

export default ROOM_TYPES.filter(type => !type.behindFeatureFlag || features.enabled(type.behindFeatureFlag))

export function inferType(config) {
	const modules = config.module_config.reduce((acc, module) => {
		acc[module.type] = module
		return acc
	}, {})
	const findByModule = module => ROOM_TYPES.find(type => type.startingModule === module)

	// infer media rooms by primary content
	const mediaRoomType = ROOM_TYPES.find(type => (type.inferModules || (type.videoChannel ? [type.startingModule] : [])).some(module => modules[module]))
	if (mediaRoomType) return mediaRoomType

	// non-media rooms should only have one module
	if (config.module_config.length === 1) {
		return findByModule(config.module_config[0].type)
	}
}

// TODO clean up with `inferType` function
export function inferRoomType(room) {
	return inferType({module_config: room.modules})
}
