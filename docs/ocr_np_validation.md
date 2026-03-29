# OCR NP Offline Validation

当前仓库已经接入实际可运行的 NP OCR，而不是未来占位方案。

## 作用

这份说明只保留离线检查入口：

- 样本清单：[test_image/ocr_np_samples.jsonl](/D:/VSCodeRepository/Lumina/test_image/ocr_np_samples.jsonl)
- 批量检查脚本：[scripts/ocr_np_batch_check.py](/D:/VSCodeRepository/Lumina/scripts/ocr_np_batch_check.py)
- 主读取入口：[core/battle_ocr.py](/D:/VSCodeRepository/Lumina/core/battle_ocr.py)

## 当前约定

- 读取入口：`core.battle_ocr.BattleOcrReader`
- 方法：`read_np_values(image_path) -> list[int]`
- 返回值固定为三项，对应前排三位从者的 NP 结果

## 样本清单格式

每一行是一个 JSON 对象，字段如下：

- `image`：仓库内相对路径
- `expected_np`：三位从者 NP 期望值
- `note`：可选备注

`expected_np` 中允许出现 `null`，表示该样本暂时还没补完标注。

## 使用说明

运行批量检查脚本后，应重点看：

- 三位从者是否串位
- `>=100` 的结果是否稳定
- 失败样本是否方便回看和继续补标
