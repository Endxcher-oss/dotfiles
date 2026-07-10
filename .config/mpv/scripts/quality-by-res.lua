-- quality-by-res.lua
-- 精准监听分辨率变化，只有宽或高真正改变时才切换配置
--
-- high-quality 比默认多这三项:
--   scale=ewa_lanczossharp       (默认: lanczos)
--   hdr-peak-percentile=99.995  (默认: 0)
--   hdr-contrast-recovery=0.30  (默认: 0)

local mp = require("mp")

local last_w, last_h = 0, 0

local function apply_quality(w, h)
    if not w or not h or w == 0 or h == 0 then
        return
    end

    if w == last_w and h == last_h then
        return  -- 分辨率未变化，跳过
    end
    last_w, last_h = w, h

    if w >= 3840 or h >= 2160 then
        mp.set_property("scale", "lanczos")
        mp.set_property("hdr-peak-percentile", "0")
        mp.set_property("hdr-contrast-recovery", "0")
        mp.msg.info(string.format("4K (%dx%d) → default scaler", w, h))
    else
        mp.set_property("scale", "ewa_lanczossharp")
        mp.set_property("hdr-peak-percentile", "99.995")
        mp.set_property("hdr-contrast-recovery", "0.30")
        mp.msg.info(string.format("Non-4K (%dx%d) → high-quality scaler", w, h))
    end
end

-- 只跟踪宽/高，不放整个 dict，避免无关字段（如色彩、sar）变化误触发
mp.observe_property("video-params/w", "number", function(_, val)
    if not val then return end
    local h = mp.get_property_number("video-params/h", 0)
    apply_quality(val, h)
end)

mp.observe_property("video-params/h", "number", function(_, val)
    if not val then return end
    local w = mp.get_property_number("video-params/w", 0)
    apply_quality(w, val)
end)
