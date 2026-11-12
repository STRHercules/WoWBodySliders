-- Use the existing BodySlider palette and Friz Quadrata typeface.
local style = {}
BodySliderSL.Style = style
style.GOLD, style.TEXT, style.MUTED = {0.91, 0.77, 0.42}, {0.88, 0.86, 0.80}, {0.60, 0.59, 0.55}
style.INK, style.BORDER = {0.03, 0.04, 0.055}, {0.54, 0.43, 0.18}
function style.Solid(parent, layer, color, alpha)
    local texture = parent:CreateTexture(nil, layer)
    texture:SetTexture("Interface\\Buttons\\WHITE8X8")
    texture:SetVertexColor(color[1], color[2], color[3], alpha or 1)
    return texture
end
function style.Text(parent, size, color)
    local text = parent:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    text:SetFont("Fonts\\FRIZQT__.TTF", size)
    text:SetTextColor(color[1], color[2], color[3])
    return text
end
function style.Border(frame)
    for _, side in ipairs({{"TOPLEFT", "TOPRIGHT"}, {"BOTTOMLEFT", "BOTTOMRIGHT"},
                           {"TOPLEFT", "BOTTOMLEFT"}, {"TOPRIGHT", "BOTTOMRIGHT"}}) do
        local line = style.Solid(frame, "BORDER", style.BORDER)
        line:SetPoint(side[1], frame, side[1]); line:SetPoint(side[2], frame, side[2])
        if side[1] == "TOPLEFT" and side[2] == "BOTTOMLEFT" or side[1] == "TOPRIGHT" then line:SetWidth(1)
        else line:SetHeight(1) end
    end
end
