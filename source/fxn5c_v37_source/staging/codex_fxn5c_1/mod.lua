local roofAnimation26 = require "fxn5c_animation_v26"
-- Only these exact model resource IDs belong to this catalogue.
local ownModels = {
  ["vehicle/train/fxn5c.mdl"] = true,
  ["vehicle/train/fxn5c_0096.mdl"] = true,
  ["vehicle/train/fxn5c_0102.mdl"] = true,
  ["vehicle/train/fxn5c_0057.mdl"] = true,
  ["vehicle/train/fxn5c_0081.mdl"] = true,
  ["vehicle/train/fxn5c_0066.mdl"] = true,
  ["vehicle/train/fxn5c_0035.mdl"] = true,
  ["vehicle/train/fxn5c_0115.mdl"] = true,
  ["vehicle/train/fxn5c_jinwen.mdl"] = true,
  ["vehicle/train/fxn5c_jinwen_7005.mdl"] = true,
  ["vehicle/train/fxn5c_menu_cr.mdl"] = true,
  ["vehicle/train/fxn5c_menu_jinwen.mdl"] = true,
}

local function ownModel(fileName)
  if type(fileName) ~= "string" then return false end
  local path = fileName:gsub("\\", "/")
  -- loadModel can supply a mod-directory prefix or a resource-relative path.
  -- Never match just a basename or an fxn5c substring/prefix.
  local relative = path:match("^res/models/model/(.+)$")
    or path:match("/res/models/model/(.+)$") or path
  return ownModels[relative] == true
end

function data()
return {
  info = {
    name = _("MOD_NAME"),
    description = _("MOD_DESC"),
    authors = { { name = "[ihtw] DisguiseMyse1f / Manfredss", role = "CREATOR", }, },
    minorVersion = 37,
    severityAdd = "NONE",
    severityRemove = "WARNING",
    tags = { "Vehicle", "Train", "Locomotive", "Diesel", "Asia" },
    params = {
      roofAnimation26.parameter(_),
      {
        key = "codex_fxn5c_year_policy",
        name = _("FXN5C_YEAR_POLICY_NAME"),
        tooltip = _("FXN5C_YEAR_POLICY_TOOLTIP"),
        uiType = "COMBOBOX",
        values = { _("FXN5C_YEAR_IGNORE"), _("FXN5C_YEAR_KEEP"), },
        defaultIndex = 0,
      },
    },
  },
  runFn = function(settings, modParams)
    local params = modParams and modParams[getCurrentModId()] or {}
    local policy = params["codex_fxn5c_year_policy"] or 0
    -- Keep the modifier for animation choices even when preserving years.
    local animationMode = params["codex_fxn5c_roof_animation"] or 0
    addModifier("loadModel", function(fileName, model)
      if not ownModel(fileName) or type(model) ~= "table" then return model end
      roofAnimation26.apply(model, animationMode)
      local metadata = model.metadata
      if policy ~= 1 and type(metadata) == "table" and type(metadata.availability) == "table" then
        metadata.availability.yearFrom = 0
        metadata.availability.yearTo = 0
      end
      return model
    end)
  end,
}
end
