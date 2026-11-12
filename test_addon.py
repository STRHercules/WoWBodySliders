from pathlib import Path
import unittest
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parent / "Interface/AddOns/BodySlider"


class AddonTests(unittest.TestCase):
    def client(self):
        lua = LuaRuntime()
        lua.execute('''
            function UnitGUID() return "Player-1-123" end
            function UnitExists() return true end
            function GetRealmName() return "Test realm" end
            BodySliderDB = {presets={keep=true}, legacy={Height=.2}}
            calls, resets, messages = {}, 0, {}
            function attach()
                C_BodySliderSL = {
                    Status=function() return 2, "test", "ready" end,
                    Backend=function() return 3 end,
                    Reset=function() resets=resets+1; return true end,
                    SetSize=function(value) calls[#calls+1]=value; return true end,
                }
            end
            SlashCmdList, UISpecialFrames, frames = {}, {}, {}
            DEFAULT_CHAT_FRAME={AddMessage=function(self,text) messages[#messages+1]=text end}
        ''')
        lua.execute((ROOT / "State.lua").read_text())
        return lua

    def test_late_attach_validation_reset_and_existing_settings(self):
        lua = self.client()
        lua.execute('''
            assert(BodySliderSL.Load())
            assert(not BodySliderSL.Tick() and not BodySliderSL.ready)
            attach(); assert(BodySliderSL.Tick() and BodySliderSL.ready)
            assert(resets==1 and calls[#calls]==1)
            assert(BodySliderSL.SetSize(1.25) and calls[#calls]==1.25)
            assert(not BodySliderSL.SetSize(0/0) and not BodySliderSL.SetSize(5))
            assert(BodySliderSL.size==1.25)
            BodySliderSL.Reset(); assert(calls[#calls]==1)
            assert(BodySliderDB.presets.keep and BodySliderDB.legacy.Height==.2)
            assert(BodySliderDB.shadowlands["Test realm:Player-1-123"].size==1)
            BodySliderSL.LeaveWorld(); assert(not BodySliderSL.ready)
            C_BodySliderSL=nil; assert(not BodySliderSL.Tick())
            attach(); assert(BodySliderSL.Tick())
            C_BodySliderSL.SetSize=function() return false, "no player model" end
            assert(not BodySliderSL.Tick() and BodySliderSL.message=="no player model")
        ''')

    def test_bad_saved_value_and_native_errors_are_not_presented_as_ready(self):
        lua = self.client()
        lua.execute('''
            BodySliderDB.shadowlands={["Test realm:Player-1-123"]={size=0/0}}
            BodySliderSL.Load(); assert(BodySliderSL.size==1)
            attach(); C_BodySliderSL.SetSize=function() error("not ready") end
            assert(not BodySliderSL.Tick() and not BodySliderSL.ready)
            C_BodySliderSL.Status=function() return 99 end
            assert(not BodySliderSL.Tick())
        ''')

    def test_retired_alpha_api_is_reset_and_not_enabled(self):
        lua = self.client()
        lua.execute('''
            attach(); C_BodySliderSL.Status=function() return 1 end
            BodySliderSL.Load(); assert(resets==1)
            assert(not BodySliderSL.Tick() and not BodySliderSL.ready and #calls==0)
        ''')

    def test_retired_matrix_only_api_is_reset_and_not_enabled(self):
        lua = self.client()
        lua.execute('''
            attach(); C_BodySliderSL.Backend=nil
            BodySliderSL.Load(); assert(resets==1)
            assert(not BodySliderSL.Tick() and not BodySliderSL.ready and #calls==0)
        ''')

    def test_new_source_backend_starts_neutral_and_preserves_prior_setting(self):
        lua = self.client()
        lua.execute('''
            BodySliderDB.shadowlands={["Test realm:Player-1-123"]={size=1.5}}
            BodySliderSL.Load()
            local store=BodySliderDB.shadowlands["Test realm:Player-1-123"]
            assert(BodySliderSL.size==1 and store.previousSize==1.5 and store.backend==3)
            BodySliderSL.SetSize(1.2); BodySliderSL.Load(); assert(BodySliderSL.size==1.2)
        ''')

    def test_ui_command_enables_only_ready_controls_and_changes_native_size(self):
        lua = self.client()
        lua.execute('''
            local function object(name)
                local o={scripts={},shown=true}
                function o:SetScript(key,fn) self.scripts[key]=fn end
                function o:SetValue(v) self.value=v; if self.scripts.OnValueChanged then self.scripts.OnValueChanged(self,v) end end
                function o:Enable() self.enabled=true end
                function o:Disable() self.enabled=false end
                function o:SetText(v) self.text=v end
                function o:Hide() self.shown=false end
                function o:IsShown() return self.shown end
                function o:Show() self.shown=true; if self.scripts.OnShow then self.scripts.OnShow(self) end end
                function o:CreateTexture() return object() end
                function o:CreateFontString() return object() end
                return setmetatable(o,{__index=function(_,key) if key:match("^%u") then return function() end end end})
            end
            UIParent=object()
            function CreateFrame(kind,name,parent,template)
                local frame=object(name); frames[#frames+1]=frame
                if name then _G[name]=frame end
                if template=="OptionsSliderTemplate" then
                    _G[name.."Low"],_G[name.."High"],_G[name.."Text"]=object(),object(),object()
                end
                return frame
            end
        ''')
        for name in ("Style.lua", "BodySlider.lua"):
            lua.execute((ROOT / name).read_text())
        lua.execute('''
            local driver=frames[1]
            driver.scripts.OnEvent(driver,"PLAYER_LOGIN")
            SlashCmdList.BODYSLIDER("")
            assert(BodySliderSLWindow:IsShown() and not BodySliderSLSize.enabled)
            attach(); driver.scripts.OnUpdate(driver,.2)
            assert(BodySliderSLSize.enabled)
            BodySliderSLSize:SetValue(1.2)
            assert(math.abs(calls[#calls]-1.2)<.0001)
            SlashCmdList.BODYSLIDER("reset"); assert(calls[#calls]==1)
            SlashCmdList.BODYSLIDER("status"); assert(#messages==1)
            driver.scripts.OnEvent(driver,"PLAYER_LEAVING_WORLD"); assert(not BodySliderSL.ready)
        ''')


if __name__ == "__main__": unittest.main()
