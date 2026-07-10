local util = module:require 'util'
local get_room_by_name_and_subdomain = util.get_room_by_name_and_subdomain
local process_host_module = util.process_host_module

local LOGLEVEL = module:get_option_string('eventyay_end_conference_log_level', 'info')
local END_CONFERENCE_REASON = 'The meeting has been terminated'

local end_conference_component = module:get_option_string('end_conference_component')
if end_conference_component then
    module:log('warn', 'Please update your config by removing muc_end_conference module from '
     .. 'the list of loaded modules in the main virtual host.')
    module:depends('features_identity')
    return
end

module:depends('jitsi_session')

local muc_component_host = module:get_option_string('muc_component')
if muc_component_host == nil then
    module:log('error', 'No muc_component specified. No muc to operate on!')
    return
end

local main_virtual_host = module:get_option_string('muc_mapper_domain_base')
if not main_virtual_host then
    module:log('warn', 'No "muc_mapper_domain_base" option set, disabling end conference component.')
    return
end

local function affiliation_from_token(session)
    if not session or not session.auth_token then
        return nil
    end

    local context_user = session.jitsi_meet_context_user
    if not context_user then
        return 'member'
    end

    if context_user['affiliation'] == 'owner'
        or context_user['affiliation'] == 'moderator'
        or context_user['affiliation'] == 'teacher'
        or context_user['moderator'] == true
        or context_user['moderator'] == 'true' then
        return 'owner'
    end

    return 'member'
end

module:log('info', 'Starting Eventyay guarded end_conference for %s', muc_component_host)

function on_message(event)
    local session = event.origin

    if event.stanza.attr.type == 'error' then
        return
    end

    if not session or not session.jitsi_web_query_room then
        return false
    end

    local moderation_command = event.stanza:get_child('end_conference')
    if moderation_command then
        local room = get_room_by_name_and_subdomain(session.jitsi_web_query_room, session.jitsi_web_query_prefix)

        if not room then
            module:log('warn', 'No room found for %s/%s',
                    session.jitsi_web_query_prefix, session.jitsi_web_query_room)
            return false
        end

        local from = event.stanza.attr.from
        local occupant = room:get_occupant_by_real_jid(from)
        if not occupant then
            module:log('warn', 'No occupant %s found for %s', from, room.jid)
            return false
        end

        local token_affiliation = affiliation_from_token(session)
        if token_affiliation == 'member' then
            module:log(LOGLEVEL, 'eventyay blocked end conference for token member %s in %s', from, room.jid)
            return false
        end

        if token_affiliation == 'owner' or occupant.role == 'moderator' then
            room:destroy(nil, END_CONFERENCE_REASON)
            module:log('info', 'Room %s destroyed by occupant %s', room.jid, from)
            return true
        end

        module:log('warn', 'Occupant %s is not moderator and not allowed this operation for %s', from, room.jid)
        return false
    end

    return false
end

module:hook('message/host', on_message)

process_host_module(main_virtual_host, function(host_module)
    module:context(host_module.host):fire_event('jitsi-add-identity', {
        name = 'end_conference'; host = module.host;
    })
end)
