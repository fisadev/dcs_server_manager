local socket = require("socket")
local url = require("url") -- defines socket.url, which socket.http looks for
local http = require("socket.http")
local ltn12 = require("ltn12")

local DsmHooks = {
    update_interval = 10,  -- seconds
    last_update = 0,
    dsm_endpoint = "http://%HOST%/dcs/mission_status",
}

DsmHooks.post_status = function()
    local mission = DCS.getMissionName() or "Unknown"
    local players = {}

    for id, player in pairs(net.get_player_list() or {}) do
        local name = net.get_player_info(id, 'name') or 'Unknown'
        table.insert(players, name)
    end

    local body = {
        mission = mission,
        players = players
    }

    local body_as_json = net.lua2json(body)

    http.request{
        url = DsmHooks.dsm_endpoint,
        method = "POST",
        headers = {
            ["Content-Type"] = "application/json",
            ["Content-Length"] = tostring(#body_as_json)
        },
        source = ltn12.source.string(body_as_json),
        create = function()
            local req_sock = socket.tcp()
            req_sock:settimeout(1, 'b')  -- no activity timeout
            req_sock:settimeout(2, 't')  -- total request timeout
            return req_sock
        end
    }
end

DsmHooks.onSimulationFrame = function()
    local now = socket.gettime()
    if now - DsmHooks.last_update > DsmHooks.update_interval then
        DsmHooks.last_update = now
        local result, err = pcall(DsmHooks.post_status())
        if not result then
            net.log("Error posting status to DSM: " .. tostring(err))
        end
    end
end

DCS.setUserCallbacks(DsmHooks)
net.log("DCS Server Manager hooks loaded")
