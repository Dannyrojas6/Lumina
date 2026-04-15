# Lumina git 提交规则

这个 skill 只服务当前仓库的本地提交。

## 固定规则

- 扫描整个工作区，包括 `tracked / unstaged / untracked`
- 按主题提出一个或多个提交组
- 模糊支持文件先进入 `review_candidates`
- 只有在人工复核后仍无法归属时，才作为未归组文件阻断
- 不回退、不清理无关改动
- 只在你确认某一组后，才暂存那一组文件
- 提交前必须重新执行该组验证命令
- 优先使用 `uv run ...`
- 没有本次验证记录时，不允许假设“已经通过”

## 分组规则

- `core/*` 与 `scripts/*` 作为主主题文件
- `skill/*` 作为独立主主题文件
- `docs / tests / config / assets / root-meta` 作为支持型文件
- `test_image/` 作为 `test-fixtures`，属于可提交的实机样本
- 支持型文件只有在**能唯一附着到一个主主题**时，才允许跟随该组
- 如果支持型文件存在多个合理归属，先进入 `review_candidates`
- `review_candidates` 由 agent 审核差异后给出建议归属，再交人工确认
- 如果工作区没有主主题文件，可以形成支持型独立组：
  - `docs`
  - `tests`
  - `test-fixtures`
  - `config`
  - `assets`
  - `root-meta`
- 已知本地备注文件不作为提交候选：
  - `TODO.md`
  - `Pro项目指导文档.md`
  - `DevLog.md`
  - `DevRecord.md`
- 同一文件如果在人工复核后仍无法明确归入唯一组，直接阻断，不做 patch 拆分

## 验证矩阵

| 提交组 | 建议验证 |
| --- | --- |
| `docs` | 可不跑代码验证 |
| `tests` | 跑该组对应测试文件 |
| `test-fixtures` | 回退到全量 `uv run python -m unittest discover -s tests -v` |
| `device` | 优先跑 `test_adb_controller.py` |
| `command-card` | 优先跑 `test_command_card*.py` |
| `runtime` | 优先跑 `test_runtime*.py` |
| `battle-runtime` | 优先跑 `test_battle*.py` |
| `support-recognition` | 优先跑 `test_support*.py` |
| `skill` | 优先跑 `test_git_commit_skill.py` |
| `perception / shared / scripts / config / root-meta` | 回退到全量 `uv run python -m unittest discover -s tests -v` |
| `assets` | 当前没有可靠默认验证，直接阻断 |

说明：

- `test_image/` 下的实机图片不按普通 `assets` 处理
- 它们作为 `test-fixtures` 正式追踪，并使用全量测试作为默认验证

如果脚本给不出可靠验证命令，除 `docs` 外，一律不允许提交。

## 硬拦截

命中以下任一情况时，拒绝直接提交：

- 工作区没有改动
- 除本地备注外，没有可提交候选
- 存在部分暂存文件
- 存在人工复核后仍未归组的文件
- 某个提交组没有可靠验证命令
- 摘要无法用一行 Conventional commit 说清

## 提交信息

- 使用单行 Conventional commit
- 形式固定为 `type: summary`
- 摘要要短，但必须说清该组主题
- 如果一句话说不清，先拆分提交，不强行合并

## 执行边界

- 只做本地 `git commit`
- 不做 hunk 级自动拆分
- 不做 `git push`
- 不做 PR
- 每个提交组都要逐组确认
- 在真正执行 `git commit` 前，必须先展示检查结果与验证结果
