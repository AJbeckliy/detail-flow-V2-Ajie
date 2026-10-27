# detail-flow-V2-Ajie


**给产品图和参考图，让 AI 帮你完成一整套电商详情页。**

DetailFlow 是一个可以交给 Codex、WorkBuddy 等具备本地执行能力的 Agent 使用的 Skill。它负责拆解卖点、规划逐屏文案和画面，调用星幕画布出图，再检查、返修和整理交付。

先确认方案，再整套生成。有问题的页面在**原画布里新增节点返修**，原图和每一轮提示词都保留下来，方便随时回看。

## 实际案例

### 宠物胸背牵引套装 · 16 屏完整详情页

这是已经完成的整套详情页长图，包含首屏、卖点、使用场景、产品细节和搭配说明。可以直接打开整图，查看从第一屏到最后一屏的整体效果。

**[点击查看 16 屏完整长图](https://raw.githubusercontent.com/AJbeckliy/detail-flow-V2-Ajie/main/assets/examples/pet-harness-16-panels.png)**

<details>
<summary>展开整套长图预览</summary>

[![宠物胸背牵引套装16屏完整详情页，点击查看原图](assets/examples/pet-harness-16-panels.png)](https://raw.githubusercontent.com/AJbeckliy/detail-flow-V2-Ajie/main/assets/examples/pet-harness-16-panels.png)

</details>

同一套产品保持配色和风格统一，每一屏根据内容改变景别、构图和文字排布。展示的是实际交付图片拼接后的完整效果。

### 男士内裤 · 完整详情页

展示产品配色、面料细节、结构说明和尺码信息。点击长图可以直接查看整套页面的排版与衔接。

**[点击查看男士内裤完整长图](https://raw.githubusercontent.com/AJbeckliy/detail-flow-V2-Ajie/main/assets/examples/mens-underwear-full.png)**

<details>
<summary>展开男士内裤长图预览</summary>

[![男士内裤完整详情页，点击查看原图](assets/examples/mens-underwear-full.png)](https://raw.githubusercontent.com/AJbeckliy/detail-flow-V2-Ajie/main/assets/examples/mens-underwear-full.png)

</details>

## 它能帮你做什么

- **看懂产品和参考**：分析商品外观、结构、颜色，以及参考图的配色、光线和排版。
- **每个产品独立规划**：比例、语言、屏数和素材绑定本产品，避免串用上一产品参数。
- **先把内容讲清楚**：安排每屏的任务、卖点、文案和画面，不把整套详情页做成重复海报。
- **在审核页直接改稿**：编辑文字、调整文字框、添加批注，导出修改稿继续制作。
- **整套批量出图**：方案确认后提交全部页面；默认 8 屏，也可以指定 10、12、16 屏等数量。
- **在原画布返修**：问题页新增独立节点，旁边标出页号、返修轮次、原因和对应的原节点。
- **保留完整过程**：每轮提示词、原图、返修结果、最终选图及生成记录都有据可查。

## 开始之前

需要安装 **星幕画布 SynMew Infinite Canvas**，它负责实际生成图片。DetailFlow 通过本机 MCP 连接调用画布。

**[下载星幕画布（Windows / macOS）](https://pan.quark.cn/s/cf3c1e40528d)**

下载目录包含 Windows 和 macOS 版本，选择对应系统的安装包。

准备好一个可以读取本地文件、执行脚本和调用 MCP 的 Agent。安装依赖和连接检查可以直接交给 Agent 完成，具体见 [安装说明](references/installation.md)。

## 安装 Skill

把下面这句话发给你的 Agent：

```text
请从 https://github.com/AJbeckliy/detail-flow-V2-Ajie 安装 DetailFlow。
按仓库中的安装说明完成依赖和星幕画布 MCP 连接检查。
```

也可以从仓库右上角 **Code → Download ZIP** 下载后，把解压后的整个目录交给 Agent 安装。已有旧版时让 Agent 按安装说明备份并更新。

## 怎么使用

提供产品图；有参考图、文案、尺寸参数时一并给出，然后说：

```text
使用 DetailFlow，帮我做一套 8 屏电商详情页。
图 1 是产品图，图 2 是风格参考。
先给我可编辑的文案和布局方案，确认后再出图。
```

已有完整文案时：

```text
按我提供的产品图和文案做 12 屏详情页。
保留已确认的产品信息，每屏根据内容选择不同构图。
需要返修时，留在原画布新增节点，并保留原图和原提示词。
```

你可以补充目标人群、想强调的卖点、页面数量、参考风格，以及不能出现的内容。具体参数和事实以你提供的资料为准。

## 一套详情页怎样完成

1. **分析素材**：区分商品事实与参考风格，确定整套视觉方向。
2. **规划并审核**：输出逐屏文案和布局，提供可编辑 HTML 审核页。
3. **整套生成**：确认方案后，一次提交全部正式页面。
4. **检查与返修**：检查文字、商品形状和颜色、构图及整套一致性，只处理问题页。
5. **整理交付**：输出按顺序命名的原图、选图记录和数量统计，并指明原画布及返修记录。

整页出图、补场景素材和返修都优先沿用星幕 MCP。9:16 只是默认比例，用户指定其他比例时按确认值制作；常用比例已内置，不必每次重新查询。

默认不需要先生成母版，也不强制先出两张试图。你明确要求先看一张视觉方向时，再走可选预览。

## 当前默认设置

| 项目 | 设置 |
|---|---|
| 出图模型 | PT2.5-稳定 |
| 分辨率与比例 | 1K；默认 9:16，也可指定 16:9、1:1、4:5 等比例 |
| 生成方式 | 确认方案后，整套批量提交 |
| 参考输入 | 产品与模特分角色；默认文字转译，也可选择匹配的风格/构图片段 |
| 返修方式 | 原画布新增节点，保留之前的提示词和结果 |

## 文件说明

- [SKILL.md](SKILL.md)：Agent 的工作流程和执行规则。
- [references/installation.md](references/installation.md)：安装、升级和连接星幕画布。
- [references/copy-review-editor.md](references/copy-review-editor.md)：可编辑文案与布局审核。
- [references/unified-executor.md](references/unified-executor.md)：生成、恢复、原画布返修和追溯。
- [references/reviewed-workflow.md](references/reviewed-workflow.md)：逐产品参数、参考角色、规划提醒与成图复核。
- `scripts/`：可直接运行的编译、执行、预览、统计和回归检查脚本。
- `examples/`：任务清单与布局示例。
- `assets/examples/`：实际详情页案例图。

DetailFlow 已经过多轮真实详情页生成、检查与返修使用。最终图片仍按正常流程逐张审核后交付。
