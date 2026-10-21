# GNSS Paper Radar

一个面向 **GNSS 高精度定位、电离层监测、深度学习预测、工程感知算法** 的静态论文雷达。页面结构、卡片和单篇海报的交互参考了 [haoshendong/slam3d-paper-watch](https://github.com/haoshendong/slam3d-paper-watch)，内容、领域体系和论文数据全部按本项目重建。

当前为 **第 001 期（2026-10-20）**，16 篇论文，四个领域各 4 篇。

在线地址：<https://donghulei.github.io/gnss-paper-watch/>

## 目录

```text
gnss-paper-watch/
├── index.html                     # 最新一期（首页）
├── daily/<date>/index.html        # 每一期的固定页
├── archive/index.html             # 归档（所有期号，倒序）
├── topics/<domain>/index.html     # 4 个领域页（gnss/iono/ml/perception）
├── papers/<slug>/index.html       # 单篇海报页（所有期号的并集）
├── assets/
│   ├── app.css                    # 版式 + 深色主题
│   └── app.js                     # 语言切换、领域筛选、搜索
├── data/
│   ├── domains.json               # 四个领域的名称、颜色、说明
│   └── editions/<date>.json       # 一天一期：edition 元信息 + papers 数组
├── scripts/
│   ├── build_site.py              # 从 editions/ 生成整站
│   ├── daily_update.py            # 自动生成当天一期并发布
│   └── fetch_arxiv.py             # 抓取并粗排 arXiv 候选
└── .github/workflows/daily.yml    # 每天 06:00（北京时间）自动更新
```

## 本地预览

```bash
cd gnss-paper-watch
python3 -m http.server 8000
# 打开 http://localhost:8000/
```

站点是纯静态的，不需要 Node、数据库或后端。字体从 Google Fonts 加载，离线时会退回系统字体。

## 领域是怎么定的

不是先拍脑袋列关键词，而是从飞书「电离层工作」知识库的项目主线反推：

| 知识库中的项目/资产 | 主要问题 | 归入领域 |
|---|---|---|
| 中国区域北斗/GNSS 电离层定位风险与完好性预警 | 视线级扰动 → 模式条件定位退化 → 处置复盘 | GNSS 高精度定位 + 工程感知 |
| ROTI 与 PPP 定位恢复研究 | ROTI 回落与 PPP 恢复的时序失配、弧段状态增量 | GNSS 高精度定位 + 电离层监测 |
| CDSF-NET 高纬 ROTI 短时预报 | 条件物理融合、扰动尾部、独立台站泛化 | 深度学习预测 |
| DORIS-ROTI | 低轨双频 TEC/ROTI、tandem 重复性、DORIS–GNSS 互补 | 电离层监测 |
| ISMR 闪烁监测接收机 | 50/100 Hz 闪烁、Septentrio M3、ARM64 采集链路 | 电离层监测 + 工程感知 |
| C08 产品对比 / BDS SSR | 改正数产品、PPP-AR 可用性 | GNSS 高精度定位 |

归纳成站点的四条主线：

1. **GNSS 高精度定位**：PPP / PPP-AR / PPP-RTK、RTK、多频多系统、模糊度、收敛、可用性、CORS/网络架构。
2. **电离层监测**：TEC / ROTI / GIX、闪烁、磁暴响应、SED/等离子体层、DORIS/ISMR 观测。
3. **深度学习预测**：TEC/ROTI 时序预报、图神经网络、Transformer、可解释性与不确定性。
4. **工程感知算法**：观测质量、多路径/NLOS、干扰与欺骗、完好性、鲁棒估计、传感器融合。

## 内容怎么维护

一期一个文件：`data/editions/<date>.json`，结构是 `{"edition": {…}, "papers": [ … ]}`。领域定义在 `data/domains.json`，所有期号共用。

人工精读的论文按下面的字段写（`essence` 必须正好 4 项）：

```json
{
  "id": "2604.18379",
  "slug": "arxiv-2604.18379",
  "domain": "ml",
  "date": "2026-04-20",
  "score": 96,
  "tier": "核心推荐",
  "title_zh": "……",
  "title_en": "……",
  "authors": ["……"],
  "cats": ["cs.LG"],
  "tags": ["ROTI", "动态图"],
  "one_liner": "一句话结论",
  "one_liner_en": "One-sentence takeaway",
  "lead_zh": "两到三句中文导语",
  "lead_en": "Two or three English sentences",
  "metrics": [{"value": "0.55", "label": "Brier Skill Score", "label_en": "Brier Skill Score"}],
  "problem": ["研究问题段落"],
  "method": ["方法段落"],
  "essence": [{"h": "是不是新算法？", "p": "……"}],
  "results": ["结果段落"],
  "limits": ["局限段落"],
  "relevance": ["与你研究路线的关系"],
  "abstract_en": "arXiv 英文摘要",
  "links": {"abs": "https://arxiv.org/abs/2604.18379", "pdf": "https://arxiv.org/pdf/2604.18379"}
}
```

改完后重新生成：

```bash
python3 scripts/build_site.py
```

生成器会读取 `data/editions/` 下所有期号，重建 `index.html`（最新一期）、`daily/<date>/`（每期一页）、`archive/index.html`（全部期号）、`papers/`（所有期号的并集，同 slug 取最新一期）、`topics/`（按最新一期）和 `404.html`。

### 每天自动一期

`scripts/daily_update.py` 负责"抓 arXiv → 初筛 → 写当期 JSON → 构建 → 提交推送"：

```bash
python3 scripts/daily_update.py --no-push          # 只在本地生成，看效果
python3 scripts/daily_update.py                    # 生成并推送（会触发 Pages 重建）
python3 scripts/daily_update.py --date 2026-10-22 --per-domain 3 --min-score 50
```

同一天重复运行会跳过（已存在 `<date>.json`），要重跑加 `--force`。没有新候选时直接退出，不会产生空期号。

自动条目带 `"auto": true`，页面上会显示「机器初筛」徽标，单篇页只给原文摘要与来源，不编造中文解读。要把它变成人工精读，就把同一篇改写成上面的人工字段并去掉 `auto`。

### 人工改某一期

直接编辑对应的 `data/editions/<date>.json`，然后 `python3 scripts/build_site.py && git push`。归档、领域页和单篇页都会跟着更新。

## 每日候选抓取

`scripts/fetch_arxiv.py` 只做 **候选发现和粗排**，不自动写中文摘要：

```bash
python3 scripts/fetch_arxiv.py --days 21 --max 60 --min-score 45
# 输出 data/candidates-YYYY-MM-DD.json
```

脚本会：

- 按四个领域分别查询 arXiv；
- 用领域锚点做硬门槛（例如感知领域必须出现 GNSS/GPS/BDS 且出现多路径/干扰/完好性等词）；
- 用标题锚点和命中词数量打分；
- 去掉已在 `data/papers.json` 中的论文；
- 输出标题、作者、摘要、分类、匹配词和 abs/PDF 链接。

建议流程：平时不用管，`daily_update.py` 会自动跑。想人工接管时，先看 `data/candidates-<date>.json`，读摘要后把值得的论文改写成人工条目。

## 发布与自动更新

站点是纯静态目录，任何静态托管都能直接用。目前两个出口：

**1. GitHub Pages（主站，已上线）**

- 地址：<https://donghulei.github.io/gnss-paper-watch/>
- 仓库：<https://github.com/DongHuLEI/gnss-paper-watch>（public）
- Pages 从 `main` 分支根目录直接取文件，`.nojekyll` 让 GitHub 跳过 Jekyll。push 后一两分钟自动重新发布。

**2. Surge（备用镜像）**

- 地址：<https://gnss-paper-watch.surge.sh>
- 更新：`npx surge . gnss-paper-watch.surge.sh`
- 账号是发布时用 `643845296@qq.com` 注册的；注册后需要在邮箱里点一次验证链接，站点才会长期保留，否则会被回收。GitHub Pages 不受影响。Surge 不会自动更新，只是镜像。

**自动更新怎么跑**

`.github/workflows/daily.yml` 每天 `22:00 UTC`（北京时间 06:00）在 GitHub Actions 里执行 `daily_update.py`：抓 arXiv → 初筛 → 写 `data/editions/<当天>.json` → 构建 → 提交并推送 → Pages 重建。GitHub 的定时任务可能延迟几分钟，一般 06:00–06:30 之间完成，早于 08:00。

手动发布：

```bash
python3 scripts/build_site.py          # 重新生成静态页
git add -A && git commit -m "第 00N 期" && git push
```

所有内部链接都是相对路径，`/<repo>/` 这种子路径和自定义域名都能用；`404.html` 同理。

## 编选口径

人工精读的期号按下面五项打分（页面上简化为四段说明）：

- 领域相关性 40%
- 方法增量 25%
- 证据强度 20%
- 可复现性 10%
- 与知识库主线的连接度 5%

机器初筛的条目不打这套分：卡片上的「匹配度」只是关键词命中数，只用于排序，页面上也明确标注了「机器初筛」。

站点不把「指标更高」等同于「更值得用」。每篇都标了证据边界：单站/单事件、仿真/实测、区域/全球，以及论文没有回答的问题。摘要中没有出现的数字不补写。

## 版权与来源

- 页面版式与交互参考 `haoshendong/slam3d-paper-watch`，按其公开源码重写为本项目的深色主题。
- 论文标题、作者、英文摘要来自 arXiv 公开元数据，版权归原作者。
- 中文解读、领域分类、评分和「与你研究路线的关系」为本项目整理，不是原作者或期刊的官方表述。
- 引用论文时请以 arXiv/期刊原文为准。
