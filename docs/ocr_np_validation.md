# Battle OCR Validation Notes

这份说明只记录当前仓库里已经存在的 `OCR` 校验入口，不写未来方案。

## 当前 `OCR` 覆盖范围

当前项目里，战斗相关 `OCR` 已经实际用于：

- 当前波次
- 敌方剩余数量
- 当前回合数
- 敌方三个位 `HP`
- 前排三位从者 `NP`
- 技能冷却判断里的角落小数字

其中离线批量脚本目前只覆盖 `NP`，其余几项主要通过真实截图和运行日志验证。

## 离线检查入口

- 批量脚本：[scripts/ocr_np_batch_check.py](/D:/VSCodeRepository/Lumina/scripts/ocr_np_batch_check.py)
- 主读取入口：[core/battle_ocr.py](/D:/VSCodeRepository/Lumina/core/battle_ocr.py)
- 通用区域检查：[scripts/ocr_region_check.py](/D:/VSCodeRepository/Lumina/scripts/ocr_region_check.py)

## 当前约定

- `core.battle_ocr.BattleOcrReader.read_np_values(image_path) -> list[int]`
- 返回固定三项，对应前排三位从者
- 单项读取失败时返回 `-1`

`ocr_np_batch_check.py` 现在不再绑定仓库内默认样本清单，离线批量校验时需要手动传入 `--manifest`。

## 调试建议

- `NP` 识别不稳时，先看 [assets/screenshots/ocr](/D:/VSCodeRepository/Lumina/assets/screenshots/ocr)
- 其他战斗文字识别不稳时，优先用 [scripts/ocr_region_check.py](/D:/VSCodeRepository/Lumina/scripts/ocr_region_check.py) 直接看裁图和处理后图片
- 当前更适合继续扩充真实战斗截图样本，而不是把更多精力花在离线假样本上
