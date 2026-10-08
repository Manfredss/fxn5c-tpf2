# FXN5C v0.44 — 红色原型车、车头修正与购买图标

从 v0.37 起的累计更新：保留国铁与金温十个量产车号，加入独立的红色 FXN5C 0001。

## 修改内容

- 红色原型车使用专用车头：四盏横排顶灯、两侧竖排下灯、后移车门和配套上车梯，侧面“复兴”为约 22 mm 的实体凸字。
- 原型车窗区连续后倾、玻璃浅凹；红色过渡斜面改为单一平面，消除对角折痕。同步衔接下部车体和灯座，两端前脸扶手竖直，补齐司机室黑色分界线。
- 按俯视参考细化车顶中央盖板、检修盖、散热网分区和双排气口。量产前窗修成矩形内凹结构，窗周及两侧过渡面的边线平行；三角罩内增加喇叭。
- 补齐转向架内端砂箱并加厚至车体外沿。“复兴”字影只落在笔画右侧和下侧；国铁与原型腰线改为较暖的橙黄色。
- 全部购买图标统一水平整车侧视和简洁轨道，补齐原型车缺失的 TGA 路径。共 52 张，覆盖 11 个车号与 2 个量产分组、两套尺寸及高清版本。
- 延续风扇旋转、大散热窗固定 55° 常开、小百叶 0.8 秒波浪循环、最大 40°、近景每窗 9 片。动画为展示配置。

## 预览

![红色 FXN5C 0001 原型车](https://raw.githubusercontent.com/Manfredss/fxn5c-tpf2/main/docs/images/v0.44_prototype.png)

![车头过渡斜面及竖直前扶手](https://raw.githubusercontent.com/Manfredss/fxn5c-tpf2/main/docs/images/v0.44_cab_corner.png)

![三种涂装的侧视购买图标](https://raw.githubusercontent.com/Manfredss/fxn5c-tpf2/main/docs/images/v0.44_purchase_icons.png)

配图为原创模型原生资源的离线回读渲染。参考照片、视频、字体二进制与游戏原装展示轨道均不分发；图标轨道由项目程序生成。

## 下载

- `FXN5C_TPF2_v0.44.zip`：当前完整游戏包。
- `FXN5C_SourceKit_v0.44_Prototype.zip`：原型车 v0.44 最终场景、脚本、贴图、完整原生游戏资源及必要 v0.43 原型基线。
- `FXN5C_SourceKit_v0.42_ProductionBaseline.zip`：历史 v0.42 完整可编辑源码与基线，供修改国铁、金温量产车；它不是当前游戏安装包。
- `SHA256SUMS.txt`：最终发布附件校验值。

GitHub 自动生成的 Source code 压缩包不等于完整 SourceKit；请按需下载上述附件。未新增 FBX，仓库历史 FBX 仅代表 v0.24。直接改最终 Blender 场景不会自动进入增量生成器；重建依赖和顺序见[构建说明](https://github.com/Manfredss/fxn5c-tpf2/blob/main/docs/BUILDING.md)。尚未完成干净解压环境的一键全量重建测试。

## 验证与使用

原生资源、源场景一致性、局部几何连接和灯口、52 张图标格式/尺寸/方向及候选包逐文件校验通过。公开副本清理场景中的个人路径并核对模型数据一致；v0.42 基线中无用户的贴图必要时启用持久保存标志，避免另存时被 Blender 丢弃，像素与模型保持一致。候选审计保留原有构建状态，最终附件以本次发布校验值为准。

本版未完成系统游戏/Model Editor 实测，原型车购买菜单仍待完整重启游戏后确认；换向灯光、行驶和紧曲线未列为已通过项目。原型车动力暂沿用量产配置，门梯在更大转向角下仍有干涉风险；连接杆、转向架、车钩对接及司机室仍待完善。模型尺寸为参考拟合。

更新前备份存档，完全退出并重启游戏。清空购买筛选后搜索“0001”或“红色原型车”；它是独立项，不在两个量产分组中。不要同时启用相同资源 ID 的本地版与工坊版。

## English

v0.44 adds the separate red FXN5C 0001 prototype and cumulative roof, recessed rectangular windshield, covered-horn, sandbox and livery refinements. The latest changes correct planar cab transitions and vertical front handrails, and supply 52 side-view TGA purchase icons. Native/static and source checks passed; in-game purchase visibility and driving validation remain pending. The prototype temporarily reuses production performance. Previews are offline renders.

Original program logic: MIT. Original models, textures, asset data and project previews: CC BY-NC-SA 4.0. Third-party marks, fonts and reference media retain their own rights.

[创意工坊](https://steamcommunity.com/sharedfiles/filedetails/?id=3804171278) · [源码仓库](https://github.com/Manfredss/fxn5c-tpf2)
