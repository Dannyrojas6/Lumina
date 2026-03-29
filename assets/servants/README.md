# Servant Assets

当前 `assets/servants/<servant_name>/` 主要承担两类内容：

- 助战头像模板：`support/portrait.png`
- 从者资料：`manifest.yaml`

最小目录结构示例：

`assets/servants/morgan/support/portrait.png`

`manifest.yaml` 当前主要描述：

- 技能序号
- 效果标签
- 目标类型
- 优先标签

当前战斗内九个技能位的可用性判断，不依赖这里的战斗技能模板。
也就是说，后续如果要继续稳住技能判断，优先补真实战斗截图和识别逻辑，不要先给每个从者手工准备战斗技能图。
