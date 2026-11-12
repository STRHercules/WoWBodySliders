local addon, style = BodySliderSL, BodySliderSL.Style
local window, slider, preview, status, amount
local updating, elapsed, inWorld = false, 0, false

local function refreshModel()
    if preview and UnitExists("player") then
        preview:SetUnit("player")
        preview:SetModelScale(1) -- The native unit copy already carries the player's render scale.
        preview:SetFacing(0.4)
    end
end

local function refresh()
    if not window then return end
    updating = true
    slider:SetValue(addon.size)
    updating = false
    if addon.ready then slider:Enable() else slider:Disable() end
    amount:SetText(string.format("%.0f%%", addon.size * 100))
    status:SetText(addon.message)
end

local function createWindow()
    if window then return end
    window = CreateFrame("Frame", "BodySliderSLWindow", UIParent)
    window:SetSize(760, 500); window:SetPoint("CENTER"); window:SetFrameStrata("DIALOG")
    window:SetMovable(true); window:EnableMouse(true); window:RegisterForDrag("LeftButton")
    window:SetScript("OnDragStart", window.StartMoving)
    window:SetScript("OnDragStop", window.StopMovingOrSizing)
    local background = style.Solid(window, "BACKGROUND", style.INK, 0.98); background:SetAllPoints()
    style.Border(window)
    table.insert(UISpecialFrames, "BodySliderSLWindow")
    local title = style.Text(window, 23, style.GOLD); title:SetPoint("TOPLEFT", 24, -22); title:SetText("Body Slider")
    local subtitle = style.Text(window, 12, style.MUTED)
    subtitle:SetPoint("TOPLEFT", 25, -54); subtitle:SetText("Shadowlands · local appearance")
    local close = CreateFrame("Button", nil, window, "UIPanelCloseButton"); close:SetPoint("TOPRIGHT", -4, -4)
    local label = style.Text(window, 15, style.TEXT); label:SetPoint("TOPLEFT", 25, -110); label:SetText("Overall size")
    amount = style.Text(window, 15, style.GOLD); amount:SetPoint("TOPRIGHT", window, "TOPLEFT", 326, -110)
    slider = CreateFrame("Slider", "BodySliderSLSize", window, "OptionsSliderTemplate")
    slider:SetPoint("TOPLEFT", 30, -148); slider:SetSize(290, 20)
    slider:SetMinMaxValues(0.5, 1.5); slider:SetValueStep(0.01); slider:SetObeyStepOnDrag(true)
    _G.BodySliderSLSizeLow:SetText("50%"); _G.BodySliderSLSizeHigh:SetText("150%")
    _G.BodySliderSLSizeText:SetText("")
    slider:SetScript("OnValueChanged", function(_, value)
        if updating then return end
        addon.SetSize(value); refresh(); refreshModel()
    end)
    local reset = CreateFrame("Button", nil, window, "UIPanelButtonTemplate")
    reset:SetSize(115, 25); reset:SetPoint("TOPLEFT", 25, -206); reset:SetText("Reset size")
    reset:SetScript("OnClick", function() addon.Reset(); refresh(); refreshModel() end)
    local note = style.Text(window, 12, style.MUTED)
    note:SetPoint("TOPLEFT", 25, -258); note:SetWidth(300); note:SetJustifyH("LEFT")
    note:SetText("Individual head, limb, waist and facial proportions are not available in this prototype.")
    status = style.Text(window, 12, style.TEXT)
    status:SetPoint("BOTTOMLEFT", 25, 28); status:SetWidth(305); status:SetJustifyH("LEFT")
    local stage = CreateFrame("Frame", nil, window); stage:SetPoint("TOPLEFT", 355, -84); stage:SetPoint("BOTTOMRIGHT", -20, 22)
    style.Border(stage)
    preview = CreateFrame("PlayerModel", nil, stage); preview:SetPoint("TOPLEFT", 1, -1); preview:SetPoint("BOTTOMRIGHT", -1, 1)
    preview:SetCamDistanceScale(1.25)
    preview:EnableMouseWheel(true)
    local distance = 1.25
    preview:SetScript("OnMouseWheel", function(_, direction)
        distance = math.max(0.5, math.min(3, distance - direction * 0.1)); preview:SetCamDistanceScale(distance)
    end)
    window:SetScript("OnShow", function() addon.Tick(); refresh(); refreshModel() end)
    window:Hide()
    refresh()
end

SLASH_BODYSLIDER1 = "/bodyslider"
SlashCmdList.BODYSLIDER = function(command)
    if command == "reset" then addon.Reset(); refresh(); refreshModel(); return end
    if command == "status" then addon.Tick(); DEFAULT_CHAT_FRAME:AddMessage("Body Slider: " .. addon.message); return end
    if not inWorld then DEFAULT_CHAT_FRAME:AddMessage("Body Slider: enter the world first."); return end
    createWindow()
    if window:IsShown() then window:Hide() else window:Show() end
end

local driver = CreateFrame("Frame")
driver:RegisterEvent("PLAYER_LOGIN"); driver:RegisterEvent("PLAYER_ENTERING_WORLD")
driver:RegisterEvent("PLAYER_LEAVING_WORLD"); driver:RegisterEvent("PLAYER_LOGOUT")
driver:RegisterEvent("UNIT_MODEL_CHANGED")
driver:SetScript("OnEvent", function(_, event, unit)
    if event == "PLAYER_LEAVING_WORLD" or event == "PLAYER_LOGOUT" then
        addon.LeaveWorld(); inWorld = false
    elseif event == "UNIT_MODEL_CHANGED" then
        if unit == "player" then addon.Tick(); refreshModel() end
    else
        inWorld = true; addon.Load(); addon.Tick(); refresh(); refreshModel()
    end
end)
driver:SetScript("OnUpdate", function(_, seconds)
    if not inWorld then return end
    local previous = addon.ready
    addon.Tick() -- Render transforms may be rebuilt by movement; reapply without accumulating scale.
    elapsed = elapsed + seconds
    if elapsed < 0.1 then return end
    elapsed = 0
    refresh()
    if previous ~= addon.ready then refreshModel() end
end)
