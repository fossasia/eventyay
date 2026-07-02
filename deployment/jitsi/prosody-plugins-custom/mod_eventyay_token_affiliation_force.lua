local LOGLEVEL = module:get_option_string('eventyay_token_affiliation_force_log_level', 'info')
local st = require 'util.stanza'
local util = module:require 'util'
local is_admin = util.is_admin
local is_healthcheck_room = util.is_healthcheck_room

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

local function set_forced_affiliation(room, occupant, affiliation, phase)
    room:set_affiliation(true, occupant.bare_jid, affiliation)
    occupant.role = room:get_default_role(affiliation) or (affiliation == 'owner' and 'moderator' or 'participant')
    module:log(LOGLEVEL, 'eventyay forced affiliation=%s role=%s for %s in %s during %s', affiliation, occupant.role, occupant.bare_jid, room.jid, phase)
end

local function apply_affiliation(room, occupant, session, phase)
    if not occupant or is_healthcheck_room(room.jid) or is_admin(occupant.bare_jid) then
        return
    end

    local affiliation = affiliation_from_token(session)
    if not affiliation then
        return
    end

    set_forced_affiliation(room, occupant, affiliation, phase)
end

local function room_has_token_owner(room)
    for _, occupant in room:each_occupant() do
        local session = prosody.full_sessions[occupant.jid]
        if affiliation_from_token(session) == 'owner' then
            return true
        end
    end

    return false
end

local function occupant_and_session_for_jid(room, real_jid)
    if not real_jid then
        return nil, nil
    end

    local occupant = room:get_occupant_by_real_jid(real_jid)
    if not occupant then
        for _, candidate in room:each_occupant() do
            if candidate.bare_jid == real_jid or candidate.jid == real_jid then
                occupant = candidate
                break
            end
        end
    end

    if not occupant then
        return nil, nil
    end

    return occupant, prosody.full_sessions[occupant.jid]
end

local enforcing = {}

local function enforce_member_if_token_requires_it(room, real_jid, phase)
    local occupant, session = occupant_and_session_for_jid(room, real_jid)
    if not occupant or is_healthcheck_room(room.jid) or is_admin(occupant.bare_jid) then
        return
    end

    local affiliation = affiliation_from_token(session)
    if affiliation ~= 'member' then
        return
    end

    local key = room.jid .. '\0' .. occupant.bare_jid
    if enforcing[key] then
        return
    end

    enforcing[key] = true
    set_forced_affiliation(room, occupant, 'member', phase)
    enforcing[key] = nil
end

local function token_requires_member(room, real_jid)
    local occupant, session = occupant_and_session_for_jid(room, real_jid)
    if not occupant or is_healthcheck_room(room.jid) or is_admin(occupant.bare_jid) then
        return false
    end

    return affiliation_from_token(session) == 'member'
end

module:hook('muc-occupant-pre-join', function(event)
    local room, occupant, session, stanza = event.room, event.occupant, event.origin, event.stanza
    if not occupant or is_healthcheck_room(room.jid) or is_admin(occupant.bare_jid) then
        return
    end

    if affiliation_from_token(session) == 'member' and not room_has_token_owner(room) then
        module:log(LOGLEVEL, 'eventyay rejected token member %s from creating %s without a token owner present', occupant.bare_jid, room.jid)
        session.send(st.error_reply(stanza, 'auth', 'registration-required', 'Waiting for moderator'))
        return true
    end
end, 1000)

module:hook('muc-occupant-pre-join', function(event)
    apply_affiliation(event.room, event.occupant, event.origin, 'pre-join')
end, -100)

module:hook('muc-occupant-joined', function(event)
    apply_affiliation(event.room, event.occupant, event.origin, 'joined')
end, -100)

module:hook('muc-set-affiliation', function(event)
    if event.affiliation ~= 'owner' then
        return
    end

    if token_requires_member(event.room, event.jid) then
        event.affiliation = 'member'
        module:log(LOGLEVEL, 'eventyay blocked owner affiliation for token member %s in %s', event.jid, event.room.jid)
    end
end, 1000)

module:hook('muc-set-affiliation', function(event)
    if event.affiliation ~= 'owner' then
        return
    end

    enforce_member_if_token_requires_it(event.room, event.jid, 'set-affiliation')
end, -100)
