# Servant Assets

当前 `assets/servants/<servant_name>/` 主要承担两类内容：

- 助战头像原图：`support/source/f_*.png`
- 离线参考库：`support/generated/reference_bank.npz`、`support/generated/reference_meta.json`
- 从者资料：`manifest.yaml`

以 Morgan 为例：

- `assets/servants/morgan/support/source/f_7040000.png`
- `assets/servants/morgan/support/generated/reference_bank.npz`
- `assets/servants/morgan/support/generated/reference_meta.json`

`support/generated/` 现在只保留离线参考库文件，不再生成旧的 `support/generated/<source_name>/` 分组模板。

`manifest.yaml` 现在记录：

- 助战原图目录
- 离线参考库文件路径
- 从者技能资料

后续如果要补其它从者，先放原图，再生成对应的 `reference_bank.npz` 和 `reference_meta.json`。
