# 通用 API 执行

没有服务商预设、默认地址或默认模型。ZZAI 仅是历史文档测试样例，不是用户选项。用户输入地址、Key、模型，由 Agent 对照目标文档匹配以下已有协议；不匹配就停止，不现场编写适配器。

## 支持的协议
- images_sync_v1：Bearer 鉴权；图像编辑 multipart POST，model、prompt、n=1 和 image/image[] 文件字段；文生图 JSON POST；响应 data 数组包含 b64_json 或 url。路径与字段必须由目标文档核实。参考协议 https://developers.openai.com/api/reference/resources/images 。
- images_async_v1：Bearer 鉴权；multipart 上传 file 返回顶层 url；JSON 提交 model、prompt、images URL 数组、n=1；返回顶层 id/task_id；GET 查询 data.status 为 NOT_START/SUBMITTED/IN_PROGRESS/SUCCESS/FAILURE；成功图为 data.result_url。这是通用结构匹配，不是厂商预设。
其他鉴权、流式、聊天出图或不匹配的异步格式均停止。只有文生图不满足商品参考图需求；必须核实用户所选模型支持参考图及数量、尺寸、格式限制，不能复制星幕参数。

## 内部配置
用户仅提供地址、Key、模型；其余由 Agent 从实际文档提取，不伪造兼容证据。路径相对 base_url；用户地址可含 /v1，不能重复拼接。示意：
```json
{
 "backend":"api","base_url":"https://USER_HOST/v1","model":"USER_MODEL",
 "protocol":"images_sync_v1","key_env":"DETAIL_FLOW_API_KEY",
 "paths":{"check":"models","generate":"images/generations","edit":"images/edits"},
 "check_kind":"models","image_field":"image[]",
 "max_images":8,"max_image_bytes":20000000,"image_formats":["png","jpeg","webp"],
 "parameters":{"size":["1024x1536"],"quality":["high"]},
 "evidence":{"source":"VERIFIED_PROVIDER_DOC_URL","reference_images":true,"model":"USER_MODEL","notes":"实际协议、模型和只读检查依据"}
}
```
参数取值必须来自文档。异步模式须配置 upload 与含 {id} 的 status 路径，无需 edit。只读检查支持 data[].id 模型列表，或 data 账户结构（check_kind=account）；后者只证明鉴权，模型支持仍需文档证据。没有安全检查接口则停止。回执绑定配置哈希和 Key 指纹，改动后重查。

## 执行
工具 scripts/image_api.py：
- check CONFIG RECEIPT：只读检查，失败停止，不上传、不生成。
- submit CONFIG RECEIPT REQUEST NEW_ATTEMPT --execute：不加 execute 只本地检查。REQUEST 含 prompt、images（本地绝对路径数组）、parameters（已核实参数对象）。模型来自配置，不可请求覆写。一页一任务。
- status ATTEMPT：异步单次查询；宿主按 3–5 秒有限轮询。
- download ATTEMPT：收集已成功结果；同步从保存响应取图，异步 SUCCESS 后取图。

执行前仍要确认可编辑文案排版方案、真实设计批准及付费范围，记录方案/审核回执/页号/文案/图片顺序及哈希/最终请求/授权。脚本不是批准器。按真实并发限制提交整组，不额外加首两屏门槛。
提交前写入意图；超时无 ID 时结果不确定，停止核对，不自动重发；有 ID 时仅恢复查询。下载失败只重收集。恢复使用 attempt 内原配置。返修新建 attempt，关联原任务与问题，不重写历史。
逐张检查解码、实际尺寸、商品与中文，再查看整组纵向预览。遵循当前主线交付约定：仅报告交付图数、累计图数、任务和返修次数，不计算或展示币值；原始响应仅作内部证据。不用星币统计器处理 API 记录。交付沿用用户媒体目录。

## 验证边界
文档匹配、只读鉴权和离线模拟不证明真实出图质量或所有服务可用。安装检查不产生付费任务；真实样片仅在已有生成授权范围执行。

参考图使用共享依赖 Pillow 解码检查，image_formats 必须来自所选模型文档；有像素限制时记录 image_dimensions（min_width/min_height/max_width/max_height），提交前检查。缺失字段不表示无限能力，Agent 必须完成文档核对。

API 方案同样保留 direct-v4 的 product_brief、逐屏主视觉/商品展示意图、ordered reference roles 与 planning checks。禁止为方便 API 而退回 v3 规划；API 不调用星幕编译器，由 Agent 检查共享契约并将已确认页面转换为请求。

请求头默认使用可识别的 DetailFlow 客户端标识。若服务商文档明确要求 User-Agent，可配置 user_agent（仅字符串，不含换行）；它绑定配置指纹，变更后重做只读检查。遇到403/1010时报告拒绝，不自动伪装浏览器、不生成临时绕过脚本；无官方允许的配置就停止。
