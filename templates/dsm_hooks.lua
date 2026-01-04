-- HOOK FROM DSM %VERSION%
local socket = require("socket")
local url = require("url") -- defines socket.url, which socket.http looks for
local http = require("socket.http")
local ltn12 = require("ltn12")

local DsmHooks = {
    update_interval = 3,  -- seconds
    last_update = 0,
    dsm_endpoint = "http://%HOST%/dcs/mission_status",
}

DsmHooks.post_status = function()
    local mission = DCS.getMissionName() or "Unknown"
    local paused = DCS.getPause()
    local players = {}

    for id, player in pairs(net.get_player_list() or {}) do
        local name = net.get_player_info(id, 'name') or 'Unknown'
        table.insert(players, name)
    end

    local body = {
        mission = mission,
        players = players,
        paused = paused
    }

    local body_as_json = net.lua2json(body)

    local response, err_or_status = http.request{
        url = DsmHooks.dsm_endpoint,
        method = "POST",
        headers = {
            ["Content-Type"] = "application/json",
            ["Content-Length"] = tostring(#body_as_json)
        },
        source = ltn12.source.string(body_as_json),
        create = function()
            local req_sock = socket.tcp()
            req_sock:settimeout(5, 'b')  -- no activity timeout
            req_sock:settimeout(7, 't')  -- total request timeout
            return req_sock
        end
    }

    if response == nil then
        -- this catches errors with the request itself
        net.log("Request error posting mission status to DSM: " .. tostring(err_or_status))
    elseif err_or_status ~= 200 then
        -- this catches errors with the response received from the server
        net.log("Response error posting mission status to DSM: " .. tostring(err_or_status) .. " -> " .. tostring(response))
    end

    if response ~= nil and response ~= "" then
        -- the response looks something like this: {"actions": ["pause", "unpause", ...]}
        local actions = net.json2lua(response).actions or {}
        for i, action in ipairs(actions) do
            net.log("Executing requested action from DSM: " .. action)
            if action == "pause" then
                DCS.setPause(true)
            elseif action == "unpause" then
                DCS.setPause(false)
            else
                net.log("Unknown action received from DSM: " .. action)
            end
        end
    end
end

DsmHooks.onSimulationFrame = function()
    local now = socket.gettime()
    if now - DsmHooks.last_update > DsmHooks.update_interval then
        DsmHooks.last_update = now
        local result, err = pcall(DsmHooks.post_status)
        if err then
            -- this catches any unexpected errors that weren't caught in the request
            net.log("Unknown error posting mission status to DSM: " .. tostring(err))
        end
    end
end

DCS.setUserCallbacks(DsmHooks)
net.log("DCS Server Manager hooks loaded")
