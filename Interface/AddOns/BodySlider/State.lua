BodySliderSL = {}
local addon = BodySliderSL
addon.size, addon.ready, addon.message = 1, false, "Waiting for the Shadowlands runtime"
local store, boundAPI

function addon.ValidSize(value)
    return type(value) == "number" and value == value and value >= 0.5 and value <= 1.5
end

function addon.Load()
    -- Retired API v1 wrote alpha, not size. Restore its baseline before ceasing calls.
    if type(C_BodySliderSL) == "table" and type(C_BodySliderSL.Status) == "function" then
        local ok, version = pcall(C_BodySliderSL.Status)
        local backendOK, backend = false, nil
        if type(C_BodySliderSL.Backend) == "function" then backendOK, backend = pcall(C_BodySliderSL.Backend) end
        if ok and (version == 1 or version == 2 and not (backendOK and backend == 3))
            and type(C_BodySliderSL.Reset) == "function" then pcall(C_BodySliderSL.Reset) end
    end
    local guid = UnitGUID("player")
    if not guid then return false end
    if type(BodySliderDB) ~= "table" then BodySliderDB = {} end
    if type(BodySliderDB.shadowlands) ~= "table" then BodySliderDB.shadowlands = {} end
    local key = (GetRealmName() or "") .. ":" .. guid
    if type(BodySliderDB.shadowlands[key]) ~= "table" then BodySliderDB.shadowlands[key] = {} end
    store = BodySliderDB.shadowlands[key]
    if store.backend ~= 3 then
        store.previousSize = store.size
        store.size, store.backend = 1, 3 -- Start the new native path at neutral; keep the previous setting for reference.
    end
    local size = tonumber(store.size)
    addon.size = addon.ValidSize(size) and size or 1
    store.size = addon.size
    return true
end

local function api()
    local native = C_BodySliderSL
    if type(native) == "table" and type(native.Status) == "function" and type(native.SetSize) == "function"
        and type(native.Reset) == "function" then
        local ok, version = pcall(native.Status)
        local backendOK, backend = false, nil
        if type(native.Backend) == "function" then backendOK, backend = pcall(native.Backend) end
        if ok and version == 2 and backendOK and backend == 3 then return native end
    end
end

function addon.Tick()
    local native = api()
    if not native then
        boundAPI, addon.ready, addon.message = nil, false, "Run the updated attach helper after Epsilon starts."
        return false
    end
    if native ~= boundAPI then
        local ok = pcall(native.Reset)
        if not ok then addon.ready, addon.message = false, "Native reset failed"; return false end
        boundAPI = native
    end
    local ok, applied, reason = pcall(native.SetSize, addon.size)
    addon.ready = ok and applied == true
    addon.message = addon.ready and "Local player size is active. Only this client sees the change."
        or (ok and (reason or "Waiting for your player model") or "Native size call failed")
    return addon.ready
end

function addon.SetSize(value)
    if not addon.ValidSize(value) then return false end
    addon.size = value
    if store then store.size = value end
    return addon.Tick()
end

function addon.Reset()
    addon.size = 1
    if store then store.size = 1 end
    local native = api()
    if native then pcall(native.Reset) end
    return addon.Tick()
end

function addon.LeaveWorld()
    local native = api()
    if native then pcall(native.Reset) end
    boundAPI, addon.ready = nil, false
end
