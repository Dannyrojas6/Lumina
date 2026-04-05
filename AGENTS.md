# Lumina AGENTS.md

## 沟通规则

- 回复只写：结论、实际变动、原因、验证结果。
- 用中文，直接说重点，不写过程叙述。
- 不用工程汇报腔，不堆术语，不绕圈子。
- 需要列点时就列点，但保持短。
- 没做完就明确说没做完；没验证就明确说没验证。
- Git 提交信息保持专业、简洁、可读，准确说明本次改动范围；不要写空泛标题，也不要写得过长。

## 执行边界

- 只改用户明确要求的范围，不顺手扩面。
- 不回退用户已有改动，按现状适配。
- 不为了方便重写整块已有逻辑，除非用户明确要求。
- 不改 [DevLog.md](/D:/VSCodeRepository/Lumina/DevLog.md) 和 [DevRecord.md](/D:/VSCodeRepository/Lumina/DevRecord.md)。
- `tests/` 当前不维护，不主动新增或扩展。

## 项目硬约束

- Lumina 只服务 `FGO`。
- 当前唯一主目标环境：`MuMu + 1920x1080`。
- 当前重点是把固定环境下的主链路做稳，不追求通用化。
- 战斗内 `NP` 判断继续走 `OCR`，不要回退到亮度方案。
- 智能战斗仍处于持续校准阶段；优先继续补稳坐标、裁图、OCR 和判断链，不优先做大规模重构。
- 任何改动都以“不破坏主链路”为前提。

## 资源与目录规则

- Python 依赖只用 `uv` 管理；不用 `pip`，除非用户明确要求。
- Python 环境与依赖操作默认只用项目根目录的 `.venv`；当前仓库已有 `.venv` 时，必须直接复用，不切到系统 Python、全局环境或其他虚拟环境。
- 当前仓库以 [pyproject.toml](/D:/VSCodeRepository/Lumina/pyproject.toml) 为准；同步依赖只用 `uv sync`。
- 默认 Python 版本按 `3.12` 处理，除非项目文件已明确要求别的版本。
- 整个任务期间只使用同一个已选中的 Python 环境，不混用项目 `.venv` 和外部环境。
- 运行 Python 脚本、测试和验证时，默认直接使用项目 `.venv\Scripts\python.exe`；除非用户明确要求，不使用 `uv run` 作为执行入口。
- 不隐式安装依赖；需要变更依赖时，明确用 `uv` 执行。
- 不在项目目录外创建额外虚拟环境。
- 不在仓库内创建 `.uv-cache/`、`.uv_cache/` 等临时缓存目录；如任务中误产生，必须清理干净。
- 仓库内公共从者资料固定在 `assets/servants/_meta/`。
- 本地从者资源目录固定在 `local_data/servants/<className>/<slug>/`。
- 从者原始图片只认 `atlas/`；`atlas/` 是唯一原始图片来源。
- `support/` 只保留运行和生成结果；原始图不放进 `support/`。
- 不允许再造 `support/source` 这类重复资源层。
- 结构变了先按当前真实状态收口，不保留过期兼容说法，除非用户明确要求。

## 验证要求

- 交付前必须验证。
- 优先用实际运行、现有脚本、日志、调试截图验证。
- 能跑项目 `.venv` 就不要拿系统里别的 Python 环境代替项目结果。
- 如果验证没做，必须明确说明。
- 不用“应该可以”“理论上没问题”替代验证结果。

## 文档分工

- AGENTS.md 只写执行约束，不写成项目手册。
- [README.md](/D:/VSCodeRepository/Lumina/README.md) 负责当前真实结构、目录、入口和资源布局。
- [DevGuide.md](/D:/VSCodeRepository/Lumina/DevGuide.md) 负责接手说明和补充背景。
- 文档优先写当前真实状态，不写空话和过期规划。
- 结构或资源规则变了，优先更新 README，不把 AGENTS.md 写成第二份 README。
