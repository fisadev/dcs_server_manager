local socket = require("socket")
local url = require("url") -- defines socket.url, which socket.http looks for
local http = require("socket.http")
local ltn12 = require("ltn12")
local json = require("dkjson") -- place dkjson.lua in same directory or adjust require path

mysocket.TIMEOUT = 2

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

    local payload = DsmHooks.get_mission_info()

    http.request{
        url = DsmHooks.dsm_endpoint,
        method = "POST",
        headers = {
            ["Content-Type"] = "application/json",
            ["Content-Length"] = tostring(#body)
        },
        source = ltn12.source.string(body),
    }
end

DsmHooks.onSimulationFrame = function()
    local now = socket.gettime()
    if now - DsmHooks.last_update > DsmHooks.update_interval then
        pcall(DsmHooks.post_status())
        DsmHooks.last_update = now
    end
end

DCS.setUserCallbacks(DsmHooks)
