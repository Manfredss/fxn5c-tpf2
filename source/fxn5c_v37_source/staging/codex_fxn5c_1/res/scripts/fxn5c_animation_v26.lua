-- FXN5C v0.26: load-time animation display choices, not temperature simulation.
-- Install as res/scripts/fxn5c_animation_v26.lua and require that name in mod.lua.
-- The caller MUST first apply its exact ownModel(fileName) resource whitelist.
local M = {}

function M.parameter(translate)
  translate = translate or function(value) return value end
  return {
    key = "codex_fxn5c_roof_animation",
    name = translate("FXN5C_ROOF_ANIMATION_NAME"),
    tooltip = translate("FXN5C_ROOF_ANIMATION_TOOLTIP"),
    uiType = "COMBOBOX",
    values = {
      translate("FXN5C_ROOF_ANIMATION_ALL"),
      translate("FXN5C_ROOF_ANIMATION_FANS"),
      translate("FXN5C_ROOF_ANIMATION_STATIC"),
    },
    defaultIndex = 0,
  }
end

function M.apply(model, mode)
  if type(model) ~= "table" or (mode ~= 1 and mode ~= 2) then return model end
  local function visit(node)
    if type(node) ~= "table" then return end
    local name = node.name
    if type(name) == "string" and type(node.animations) == "table" then
      local louver = name:match("^fxn5c_v26_louver_") ~= nil
      local fan = name:match("^fxn5c_v26_fan_") ~= nil
      if louver or (mode == 2 and fan) then
        -- Keep the node, mesh, transform, other events and numeric node IDs.
        node.animations.forever = nil
      end
    end
    for _, child in ipairs(node.children or {}) do visit(child) end
  end
  for _, lod in ipairs(model.lods or {}) do visit(lod.node) end
  return model
end

return M
