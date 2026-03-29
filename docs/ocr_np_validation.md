# Battle OCR Validation Notes

这份说明只记录当前仓库里已经存在的 `OCR` 校验入口，不写未来方案。

## 当前 `OCR` 覆盖范围

当前项目里，战斗相关 `OCR` 已经实际用于：

- 当前波次
- 敌方剩余数量
- 当前回合数
- 前排三位从者 `NP`
- 技能冷却判断里的角落小数字

其中离线批量脚本目前只覆盖 `NP`，其余几项主要通过真实截图和运行日志验证。

## 离线检查入口

- 样本清单：[test_image/ocr_np_samples.jsonl](/D:/VSCodeRepository/Lumina/test_image/ocr_np_samples.jsonl)
- 批量脚本：[scripts/ocr_np_batch_check.py](/D:/VSCodeRepository/Lumina/scripts/ocr_np_batch_check.py)
- 主读取入口：[core/battle_ocr.py](/D:/VSCodeRepository/Lumina/core/battle_ocr.py)

## 当前约定

- `core.battle_ocr.BattleOcrReader.read_np_values(image_path) -> list[int]`
- 返回固定三项，对应前排三位从者
- 单项读取失败时返回 `-1`

## 样本清单格式

每一行是一个 JSON 对象：

- `image`：仓库内相对路径
- `expected_np`：三位从者 `NP` 期望值
- `note`：可选备注

`expected_np` 里允许出现 `null`，表示该样本暂时未补完整标注。

## 调试建议

- `NP` 识别不稳时，先看 [assets/screenshots/ocr](/D:/VSCodeRepository/Lumina/assets/screenshots/ocr)
- 战斗文字或技能角落识别不稳时，优先补真实战斗截图，不要先拿网页素材代替
- 当前更适合继续扩充真实截图样本，而不是把更多精力花在离线假样本上
