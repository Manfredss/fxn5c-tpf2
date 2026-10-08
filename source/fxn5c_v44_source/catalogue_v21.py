"""Generate this mod's bilingual purchase catalogue and bounded year switch."""
from pathlib import Path
import json
from roster_v21 import ROSTER, description_key

ROOT = Path(__file__).resolve().parent
MOD_ROOT = ROOT/'staging/codex_fxn5c_1'
YEAR_KEY = 'codex_fxn5c_year_policy'
GROUPS = {'fxn5c_menu_cr': 'VEHICLE_FXN5C_MENU_CR',
          'fxn5c_menu_jinwen': 'VEHICLE_FXN5C_MENU_JINWEN'}


def catalogue_strings():
    en = {
        'MOD_NAME': 'FXN5C v0.21 — China Railway & Jinwen Railway / 10 Variants',
        'MOD_DESC': 'Ten numbered variants in two purchase groups, with an availability-year option (ignore years by default; original model years: CR 2024, Jinwen 2025). Depot markings are user-requested customizations, not certified real-world allocations or delivery dates. Refined body/roof equipment and CR/Jinwen liveries, Wei-style Fuxing lettering and connected JWR mark. Rods retain native dual-end skinning: the shaft can bend/stretch; NOT rigid mechanical IK. Automatic stopping lights and departure pre-lighting are NOT implemented. Photo-based estimates, not factory CAD. v0.21 requires in-game visual and purchase-menu verification.',
        'FXN5C_YEAR_POLICY_NAME': 'Vehicle availability years',
        'FXN5C_YEAR_POLICY_TOOLTIP': 'Only these FXN5C variants and their two purchase-group headers are affected. Ignore years: available in every game year. Keep model years: CR from 2024, Jinwen from 2025. Existing purchased vehicles are not deleted.',
        'FXN5C_YEAR_IGNORE': 'Ignore years (default)',
        'FXN5C_YEAR_KEEP': 'Keep model years (2024 / 2025)',
        'VEHICLE_FXN5C_MENU_CR_NAME': 'FXN5C — China Railway Blue',
        'VEHICLE_FXN5C_MENU_CR_DESC': 'China Railway blue: eight numbered variants. Select a vehicle within this group. Depot assignments are customized at the user’s request.',
        'VEHICLE_FXN5C_MENU_JINWEN_NAME': 'FXN5C — Jinwen Railway',
        'VEHICLE_FXN5C_MENU_JINWEN_DESC': 'Jinwen Railway blue/white/red: 7006 and 7005. Select a vehicle within this group. Depot assignments are customized at the user’s request.',
    }
    zh = {
        'MOD_NAME': '复兴5C（FXN5C）v0.21 国铁／金温铁路 · 10车号',
        'MOD_DESC': '10个车号分为国铁、金温两组购买；新增年份开关，默认忽略年份，也可保留模型设定的国铁2024年、金温2025年。车身配属为用户指定的定制标识，不代表官方配属或交付日期认证。细化车体/车顶设备及两涂装、魏碑风格复兴字样和连写JWR标志。连接杆仍为原生双端蒙皮，中段会弯曲伸缩，并非刚性机械IK；自动停车熄灯和发车预亮未实现。照片估算建模，非厂家CAD。v0.21仍需游戏内外观及购买菜单复测。',
        'FXN5C_YEAR_POLICY_NAME': '车辆可用年份',
        'FXN5C_YEAR_POLICY_TOOLTIP': '仅影响本模组10个车号及2个购买分组。忽略年份：任意游戏年份可购；保留模型年份：国铁2024年起、金温2025年起。不会删除已经购买的车辆。',
        'FXN5C_YEAR_IGNORE': '忽略年份（默认）',
        'FXN5C_YEAR_KEEP': '保留模型年份（2024／2025）',
        'VEHICLE_FXN5C_MENU_CR_NAME': '复兴5C · 国铁蓝',
        'VEHICLE_FXN5C_MENU_CR_DESC': '国铁蓝涂装，共8个车号。请在分组中选择具体车辆；配属标识按用户要求定制。',
        'VEHICLE_FXN5C_MENU_JINWEN_NAME': '复兴5C · 金温铁路',
        'VEHICLE_FXN5C_MENU_JINWEN_DESC': '金温铁路蓝白红涂装，包含7006、7005。请在分组中选择具体车辆；配属标识按用户要求定制。',
    }
    depots = {'上局沪段': 'Shanghai Bureau · Shanghai Depot',
              '上局宁东段': 'Shanghai Bureau · Nanjing East Depot',
              '上局杭段': 'Shanghai Bureau · Hangzhou Depot',
              '上局徐段': 'Shanghai Bureau · Xuzhou Depot',
              '金温 温段': 'Jinwen Railway · Wenzhou Depot'}
    for row in ROSTER:
        key=description_key(row); n=row['number']; d=row['depot']
        livery_en='Jinwen Railway' if row['jinwen'] else 'China Railway Blue'
        livery_zh='金温铁路' if row['jinwen'] else '国铁蓝'
        en[key+'_NAME']=f'FXN5C {n} — {livery_en} / {depots[d]}'
        zh[key+'_NAME']=f'复兴5C · {livery_zh} FXN5C {n} · {d}'
        en[key+'_DESC']=f'FXN5C {n}, {livery_en}; {depots[d]} markings. Co-Co diesel locomotive, 3,530 kW, 120 km/h. This depot assignment is a user-requested customization, not an officially verified allocation. Dimensions and hidden details are photo-based approximations. The connecting rod uses deforming skinning, not rigid mechanical IK.'
        zh[key+'_DESC']=f'FXN5C {n}，{livery_zh}涂装；车身配属标识“{d}”。Co-Co轴式内燃机车，3530千瓦，120公里/小时。配属按用户要求定制，非官方核验结论。部分尺寸和隐藏细节为照片估算；连接杆为会变形的蒙皮跟随，非刚性机械IK。'
    # Keep the old base keys useful for existing save/tool references.
    for lang in (en,zh):
        for old,num in (('VEHICLE_FXN5C','0051'),('VEHICLE_FXN5C_JINWEN','7006')):
            for suffix in ('_NAME','_DESC'):
                lang[old+suffix]=lang['VEHICLE_FXN5C_'+num+suffix]
    assert set(en)==set(zh)
    return {'en':en,'zh_CN':zh}


def mod_lua():
    models=[row['stem'] for row in ROSTER]+list(GROUPS)
    whitelist='\n'.join('  ["vehicle/train/'+stem+'.mdl"] = true,' for stem in models)
    return '''-- Only these exact model resource IDs belong to this catalogue.
local ownModels = {
'''+whitelist+'''
}

local function ownModel(fileName)
  if type(fileName) ~= "string" then return false end
  local path = fileName:gsub("\\\\", "/")
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
    authors = { { name = "Codex-assisted project", role = "CREATOR", }, },
    minorVersion = 21,
    severityAdd = "NONE",
    severityRemove = "WARNING",
    tags = { "Vehicle", "Train", "Locomotive", "Diesel", "Asia" },
    params = {
      {
        key = "'''+YEAR_KEY+'''",
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
    local policy = params["'''+YEAR_KEY+'''"] or 0
    -- Index 1 preserves the original MDL availability; no modifier is registered.
    if policy == 1 then return end
    addModifier("loadModel", function(fileName, model)
      if not ownModel(fileName) or type(model) ~= "table" then return model end
      local metadata = model.metadata
      if type(metadata) == "table" and type(metadata.availability) == "table" then
        metadata.availability.yearFrom = 0
        metadata.availability.yearTo = 0
      end
      return model
    end)
  end,
}
end
'''


def write_catalogue(mod_root=None):
    target=Path(mod_root) if mod_root is not None else MOD_ROOT
    target.mkdir(parents=True,exist_ok=True)
    (target/'mod.lua').write_text(mod_lua(),encoding='utf-8',newline='\n')
    blocks=[]
    for lang,values in catalogue_strings().items():
        lines=['    '+key+' = '+json.dumps(value,ensure_ascii=False)+',' for key,value in values.items()]
        blocks.append('  '+lang+' = {\n'+'\n'.join(lines)+'\n  },')
    (target/'strings.lua').write_text('function data()\nreturn {\n'+'\n'.join(blocks)+'\n}\nend\n',encoding='utf-8',newline='\n')
    return target


if __name__=='__main__':
    print(write_catalogue())
