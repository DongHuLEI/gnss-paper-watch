# GNSS × AI 研究雷达

在线地址：<https://donghulei.github.io/gnss-paper-watch/>

以 GNSS、电离层和可靠感知为主线，连接科学 AI、具身智能与模型训练。纯静态前端，Python 标准库构建，不需要数据库、运行时 Node 或浏览器内 API 密钥。

## 怎么浏览

- **研究概览**：最新一期、六领域入口、交叉视角和实际更新状态。
- **全部论文**：检索所有历史的标题、作者、摘要、标签和 arXiv ID；组合领域、交叉视角、收录月份、内容状态与阅读状态；支持排序、分页和紧凑列表。
- **领域页**：显示该领域的全部历史论文，一篇论文可以属于多个领域。
- **历史日报**：月份日历、按领域筛选、相邻期号翻页。旧的 `daily/<date>/` 和 `papers/<slug>/` 地址保留。
- **训练与学习**：训练闭环、数据与评测、SFT/LoRA、后训练、具身策略、科学 AI 六条学习路线，链接指向官方资料。
- **我的阅读**：收藏和已读只存本浏览器，不自动跨设备同步。在论文库中导出 JSON，可在另一台设备导入合并。

论文标题与速读支持中英文切换，导航和整理正文以中文为主；支持明暗主题、移动端菜单、键盘 `/` 搜索和打印阅读页。

## 六领域与交叉视角

`data/domains.json` 同时定义展示信息、arXiv 查询、领域锚点和关键词：

1. GNSS 高精度定位：PPP/PPP-AR/RTK、北斗、模糊度、完好性与低轨增强。
2. 电离层与空间天气：TEC/ROTI、闪烁、磁暴、多源观测与风险。
3. 时空预测与科学 AI：时序基础模型、图网络、物理约束与不确定性。
4. 工程感知与多源融合：SLAM、GNSS/LiDAR/IMU、NLOS、鲁棒估计与实时部署。
5. 具身智能与机器人：VLA、世界模型、机器人学习、模仿学习与 Sim-to-Real。
6. 模型训练与高效适配：预训练、SFT/LoRA、强化学习、蒸馏量化、数据与评测。

交叉视角包括不确定性、物理约束、小样本、仿真到真实、多模态和边缘部署。关键词采用单词边界，避免把 `TEC` 命中到 `detection` 等无关词。

## 内容状态与证据边界

- **检索初筛**：原始元数据和摘要，未生成中文解读。
- **AI 解读 · 待核验**：DeepSeek 基于摘要或已读取的网页摘录生成，明确显示模型、时间、阅读范围和来源；不称为全文精读。
- **整理摘要**：保留原有中文笔记和指标。旧内容未逐篇复核全文，重要数字、作者列表和配置应回到原文检查。

“匹配度”用于检索排序，不代表论文质量。旧整理分数与新关键词分数的口径不同，不能据此横向评价论文。

AI 的结果引文须在来源中逐字匹配，结果中的数字须出现在相应引文中。自动检查不能保证语义推理正确，也不能代替人工核验。研究迁移建议单独展示为推断。

## 每日更新

`.github/workflows/daily.yml` 使用 UTC `17 16,19,22 * * *`，对应北京时间 **00:17、03:17、06:17**。提前触发并补跑，目标是在早上 8 点前更新；GitHub Actions 可能延迟，不能作严格时间保证。首页显示实际检查时间，而不是固定显示“已更新”。

首次启用前，由仓库管理员在 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。不要新建示例工作流，本仓库已经有发布工作流。默认 `GITHUB_TOKEN` 不能代替管理员修改这个设置；工作流会在付费检索前检查，配置不正确时暂停，避免旧的分支发布覆盖新的部署包。

流程：检查 Pages 发布源 → 日期限定的六路 arXiv 检索 → 去重与领域均衡挑选 → 可选 DeepSeek 补充检索 → arXiv 元数据复核 → 可选网页读取与中文解读 → 保存当期与用量 → 构建、验证 → 提交数据 → 显式部署 Pages。

- 每天默认最多 12 篇，每领域最多 2 篇，不用无关稿件凑数。
- 同日已存在时不重复收录；可以补齐未生成的 AI 解读。`--force` 重新检索并补充自动期号，不覆盖人工整理条目。
- 没有新论文时不创建空期号，记录 `no_new_papers`。
- 全部来源失败时返回非零状态，保留上一期并记录 `retrieval_failed`。
- 部分失败标为 `partial`，首页与当期显示检索不完整，补跑可重试；失败不代表没有新论文。
- arXiv 查询至少间隔 8 秒；HTTP 429/5xx 按 30、60 秒退避，并遵守更长的 `Retry-After`。服务器要求等待超过 180 秒时留待下一次补跑，不提前重试。
- 无密钥、无余额、输出不完整或证据校验失败时保留原始摘要，并显示具体状态。
- Surge 旧镜像不会自动更新，不作为主站。

## 安全启用 DeepSeek

1. 在 DeepSeek 官方平台创建自己的 API 密钥并确认余额。
2. 打开仓库 **Settings → Secrets and variables → Actions → New repository secret**。
3. 名称填 `DEEPSEEK_API_KEY`，值填密钥。不要提交到代码、静态文件或聊天记录。
4. 在 **Actions → Research radar → Run workflow** 手动运行一次。
5. 查看运行摘要和站点“来源与更新说明”中的 AI 状态、解读数量及用量。

本机只有在明确设置环境变量 `DEEPSEEK_API_KEY` 时才会调用。没有配置时不调用付费接口。不会从其他软件配置中搜集凭据，也不向模型发送飞书原文或私有数据。

官方接口：

- [搜索与网页读取](https://api-docs.deepseek.com/guides/search)
- [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion)
- [实时价格](https://api-docs.deepseek.com/quick_start/pricing)

`data/settings.json` 控制模型和限额，默认 `deepseek-flash`、关闭思考，每天最多解读 10 篇、搜索 6 次、网页读取 6 次、单次最多输出 2400 token。每日 60000 token 使用请求前的保守预留控制；网络中断等不确定调用保留预留量，实际账单以服务商为准。配置是安全默认值，不是费用承诺。

同日用量持久化在 `data/usage/<date>.json`；生成结果缓存于被忽略的 `.cache/deepseek/`。认证失败或余额不足后停止后续付费请求。日志不保存 API 密钥、原始错误正文或模型思考内容。

## 本地使用

Python 3.6+，无第三方运行时依赖。构建和日更使用相同的标准库代码；Actions 使用 Python 3.11。

```bash
python3 scripts/build_site.py
python3 scripts/validate_site.py
python3 -m http.server 8000 --bind 127.0.0.1
```

本地服务仅供当前机器预览；跨设备请使用上面的公网地址。

```bash
# 检索而不发布
python3 scripts/fetch_arxiv.py --days 14 --max 60

# 生成并构建，但不提交或推送
python3 scripts/daily_update.py --no-push

# 仅准备数据
python3 scripts/daily_update.py --no-push --no-build

# 必须有可用 AI，否则明确失败
python3 scripts/daily_update.py --no-push --require-ai

# 显示状态，不执行更新
python3 scripts/daily_update.py --show-status

# 日更脚本也可以构建并提交推送，须在干净工作区明确执行
python3 scripts/daily_update.py
```

修改源数据后先构建、验证，再提交。机器人也会提交数据，所以本地编辑前先 `git pull --ff-only`。有未提交改动时不要使用破坏性重置。

## 目录与发布边界

```text
data/domains.json          六领域查询、显示信息与交叉视角
data/settings.json         公开设置、用量限额与非私有研究方向
data/learning.json         学习路线及官方链接
data/editions/<date>.json  每期数据与 AI 来源记录
data/status.json           最近运行状态
data/usage/<date>.json     脱敏用量记录
scripts/radar_config.py    配置、日期与多领域分类
scripts/fetch_arxiv.py     有重试与日期约束的元数据检索
scripts/deepseek_client.py 密钥隔离、预算、搜索读取与证据校验
scripts/daily_update.py    日更编排、去重、归档与状态
scripts/build_site.py      静态页面与公开部署包构建
scripts/validate_site.py   路由、锚点、历史完整性和发布文件校验
assets/app.css             无外部字体依赖的响应式主题
assets/app.js              筛选、分页、URL 状态、阅读数据与菜单
```

部署只上传构建器导出的 HTML、CSS、JS 和 `.nojekyll`，不复制整个项目，不上传 `data/`、脚本、缓存或 Git 元数据：

```bash
python3 scripts/build_site.py --output _site
python3 scripts/validate_site.py --root _site --public
```

导出目录必须不存在且位于项目内，避免误删其他文件。源码仓库仍是公开的，因此不要在任何被跟踪的源文件里放入隐私或密钥。404 页使用站点配置中的绝对 base，子路径错误地址也能返回主站导航。

## 来源与版权

论文元数据与摘要版权归原作者。中文整理和 AI 解读不是原作者或期刊的官方表述；引用以 arXiv 或期刊原文为准。最初参考 `haoshendong/slam3d-paper-watch` 的日报组织方式，本版页面、样式、交互和生成器已重写为研究工作台。
