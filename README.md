# GNSS Paper Radar

一个面向 **GNSS 高精度定位、电离层监测、深度学习预测、工程感知算法** 的静态论文雷达。页面结构、卡片和单篇海报的交互参考了 [haoshendong/slam3d-paper-watch](https://github.com/haoshendong/slam3d-paper-watch)，内容、领域体系和论文数据全部按本项目重建。

当前为 **第 001 期（2026-10-20）**，16 篇论文，四个领域各 4 篇。

## 目录

```text
gnss-paper-watch/
├── index.html                     # 最新一期（首页）
├── daily/2026-10-20/index.html    # 当期固定页
├── archive/index.html             # 归档
├── topics/<domain>/index.html     # 4 个领域页（gnss/iono/ml/perception）
├── papers/<slug>/index.html       # 16 个单篇海报页
├── assets/
│   ├── app.css                    # 版式 + 深色主题
│   └── app.js                     # 语言切换、领域筛选、搜索
├── data/papers.json               # 唯一的论文内容源
└── scripts/
    ├── build_site.py              # 从 JSON 生成整站
    └── fetch_arxiv.py             # 抓取并粗排每日 arXiv 候选
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

所有论文内容在 `data/papers.json`。每篇论文的字段：

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

生成器会重建 `index.html`、`daily/<date>/index.html`、`archive/index.html`、`topics/`、`papers/` 和 `404.html`。

### 新增一期

1. 复制 `data/papers.json` 为备份（例如 `data/papers-2026-10-21.json`）。
2. 修改 `edition.date`、`edition.number`、`edition.title`、`edition.overview`。
3. 替换/追加 `papers` 数组。
4. 运行 `python3 scripts/build_site.py`。
5. 归档页目前只列出 `edition` 当前期；如果要保留多期，建议让 `build_site.py` 扫描 `daily/*/index.html` 并生成归档列表（当前版本刻意保持简单）。

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

建议流程：先看候选 JSON，再人工读摘要，决定是否写入 `papers.json`。这样不会把自动摘要或错误归类直接发布。

## 部署到 GitHub Pages

站点已发布为公开静态站：

- 仓库：`https://github.com/DongHuLEI/gnss-paper-watch`
- 站点：`https://donghulei.github.io/gnss-paper-watch/`

Pages 从 `main` 分支根目录直接取文件，`.nojekyll` 让 GitHub 跳过 Jekyll。所以更新内容走一遍：

```bash
python3 scripts/build_site.py          # 重新生成静态页
git add -A && git commit -m "第 002 期" && git push
```

push 后一两分钟自动重新发布，无需其他操作。所有内部链接都是相对路径，项目页和自定义域名都能用；`404.html` 同理。

## 编选口径

- 领域相关性 40%
- 方法增量 25%
- 证据强度 20%
- 可复现性 10%
- 与知识库主线的连接度 5%

站点不把「指标更高」等同于「更值得用」。每篇都标了证据边界：单站/单事件、仿真/实测、区域/全球，以及论文没有回答的问题。摘要中没有出现的数字不补写。

## 版权与来源

- 页面版式与交互参考 `haoshendong/slam3d-paper-watch`，按其公开源码重写为本项目的深色主题。
- 论文标题、作者、英文摘要来自 arXiv 公开元数据，版权归原作者。
- 中文解读、领域分类、评分和「与你研究路线的关系」为本项目整理，不是原作者或期刊的官方表述。
- 引用论文时请以 arXiv/期刊原文为准。
