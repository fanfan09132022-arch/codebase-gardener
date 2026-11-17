# 代码库园丁 · Codebase Gardener

一个写给**不懂代码的人**的 AI skill：让 AI 帮你检查和守护一个长期维护的代码库，越改越稳，而不是越改越乱。走完全程后，部分改动可以**不经你审查代码就自动上线**。

> AI 写代码会出错，这很正常。这个 skill 不去指望 AI 不犯错，而是帮你在项目里搭起"错误过不了关"的机制。你的工作从"审代码"换成三件事：确认功能地图（什么叫对）、确认风险分级（什么必须问你）、看证据。
>
> 所以"免审"不是没人审，而是审的东西换了。这三样确认错了，机制就会稳定地放错的东西过去。

## 它能做什么

- **体检**：用大白话告诉你项目是做什么的、现在有哪些自动检查、哪里有"坏样板"（过时代码、写法不统一、临时凑合的写法），并按严重程度排序
- **设计防呆装置**：把反复出现的问题变成电脑自动执行的检查，违反了就直接报错，而不是只写一句"以后注意"
- **要求交证据**：AI 每次改完代码，都要实际运行、测试，把结果拿给你看
- **上线就绪评分**：按功能区域，逐项检查离"免审上线"还差什么
- **搭上线流水线**：检查不过就合不进主线；AI 按功能地图自动验证；每次小步上线，出事自动退回上一版
- **每条结论都有依据**：体检结果要标明依据（项目自己的多数写法、官方文档、功能地图、实际运行结果），没依据的只能算推测
- **按风险分级放权**：脚本同时看改了哪些文件、改动内容里有没有碰钱、权限、删数据、密钥、对外发送的迹象。碰到这些、改关卡本身、或者改的是没登记的目录，永远停下等你
- **信任靠记录挣来**：一个区域要先由你看着证据摘要批准上线、攒够没出事的记录，才解锁自动上线。看的是实测的变更失败率、恢复时间、错误预算，不是 AI 的自评
- **安全检查**：查代码里写进的密钥、依赖里已知的漏洞；工作流里的第三方组件按版本哈希锁定
- **埋雷测试**：故意往副本里放进已知的错误，看关卡拦下几个。雷至少来自两种来源（历史 bug、你说的担心、变异工具、另一个 AI 会话），避免出题人和检查人是同一个 AI。核心功能的雷没全拦下，就不能免审上线
- **事后追账**：上线后出的每个问题都记一笔，查清哪道关卡漏了、补上，并把这个 bug 做成新雷。出过漏网的区域自动暂停自动上线，只有你本人能恢复
- **长期园丁模式**：以后 AI 每犯一次重复的错，它都会主动问你要不要做成一条新的自动检查
- **留几本你看得懂的账本**：功能地图、守门规则、上线就绪评分、埋雷记录、漏网记录，都在项目的 `docs/` 里

## 免审上线的五项前提

| 前提 | 是什么 | 比喻 |
|---|---|---|
| 1 结构 | 不该互通的代码禁止互相调用，容易出错的写法直接禁掉 | 插头形状不对，插不进插座 |
| 2 强制关卡 | 每次提交自动跑检查和测试，不过就合不进主线 | 机场安检门 |
| 3 自动验证 | AI 改完后自己启动程序，按功能地图把核心功能走一遍，留下证据 | 新车出厂试驾 |
| 4 能退回 | 小步上线、版本留底，上线后异常自动退回 | 撤销键 |
| 5 标准答案 | 一份大白话的功能地图，写清每个功能怎样算正常 | 考试的标准答案 |

前四项 AI 可以帮你搭。第五项只能由你确认，因为它决定了前四项检查的是什么。某个功能区域五项全部达标、埋雷全部拦下、实测数字在线内，才允许那里的改动免审上线。

## 怎么知道检查准不准

AI 的判断本身没法保证对，所以这个 skill 不要求你相信它，而是用结果去量：

- **误报**（说有问题，其实没有）：每条结论都要有依据，能实际跑出来，跑不出来的只算推测
- **漏报**（真问题没发现）：用埋雷测试量"漏了多少"，用事后追账量"上线后漏网多少"
- **放不放权**：看变更失败率的 95% 置信上界。小项目上线次数少，10 次没出事可能只是运气，所以按默认值大约要连续 22 次没出事才放行。再加上恢复时间和错误预算两条线

出发点是一个简单的式子：**上线损失 ≈ 出错的概率 × 影响多少用户 × 多久发现并恢复**。人工审代码只压第一项，这个 skill 三项都压，并且三项都要量出来。

## 为不懂代码的人设计

- 全程大白话，术语都配生活中的比喻
- 前 4 个阶段**只看不改**
- 每次只提议 1 到 3 个改动，你**逐条批准**后才动手
- 改动在副本（git 分支）上进行，不碰原件
- **每道关卡都现场演示**：AI 故意制造一个错误，让你亲眼看到它被拦下。你不用读代码，也能确认关卡真的有效
- AI 不能放松自己的关卡：修改检查规则、上线设置、风险分级，永远要你批准。这一条靠权限执行，不靠 AI 自觉：AI 用一个只有写权限的独立账号，关卡配置从主线读

## 八个阶段

| 阶段 | 做什么 | 改不改代码 |
|---|---|---|
| 1 看懂项目 | 项目是干什么的，现在有哪些检查，怎么上线，哪里碰钱和数据 | 不改 |
| 2 体检 | 找坏样板、旧代码、凑合的写法 | 不改 |
| 3 设计防呆装置 | 每个问题该用哪种方式拦 | 不改 |
| 4 上线就绪评分 | 起草功能地图，按区域给五项前提打分 | 不改 |
| 5 装防呆装置 | 做你批准的那一两条，演示，交证据，记账 | 改 |
| 6 搭上线流水线 | 强制关卡、自动验证、小步上线与自动退回 | 改 |
| 7 按风险放权 | 你确认风险分级后，达标区域的低风险改动自动上线 | 改设置 |
| 8 长期园丁 | 以后每次犯错，都问要不要加关卡 | 视情况 |

只想体检和清理、不打算免审上线的话，做完阶段 5 就可以直接进入阶段 8。

## 文件结构

```
codebase-gardener/
├── SKILL.md                    AI 读的主说明：八个阶段、规则、汇报模板
├── reference/
│   ├── release-pipeline.md     上线流水线怎么搭：账号、主线保护、金丝雀、功能开关、数据库迁移、安全
│   └── measurement.md          怎么量：埋雷、事后追账、放权指标、阈值来源、每月复盘
├── scripts/                    装进项目的 .gardener/bin/，只用 Python 3.8+ 标准库
│   ├── risk_scan.py            判断改动风险等级（路径 + 内容）
│   ├── release_gate.py         判断区域能不能自动上线；记上线账本；出月报
│   ├── run_mines.py            埋雷测试；从修 bug 的提交反推新雷
│   ├── health_check.py         上线后健康检查
│   └── ledger.sh               上线账本分支的取出、保存、核查
├── templates/
│   ├── gardener-config.json    区域、风险等级、阈值
│   ├── github/                 三个 GitHub Actions 工作流 + CODEOWNERS
│   └── docs-*.md               给你看的账本模板
└── evals/                      4 个评测场景和一个假项目
```

## 怎么安装

**Claude（网页或桌面版）**
1. 下载本仓库的 `codebase-gardener` 文件夹，打包成 ZIP
2. 打开 Claude，进入 **Customize > Skills**，点 **"+"**，再点 **"+ Create skill" > "Upload a skill"**
3. 上传这个 ZIP

**Claude Code**
把 `codebase-gardener` 文件夹放进 `~/.claude/skills/`（对所有项目生效），或者放进项目里的 `.claude/skills/`（只对这个项目生效）。

**Cursor 等其他工具**
把 `codebase-gardener/SKILL.md` 复制到你项目的根目录，改名为 `AGENTS.md`。

## 怎么用

在 Claude Code 里打开你的项目，说一句：

> 用代码库园丁帮我检查这个项目

想走到免审上线，就说：

> 用代码库园丁帮我把这个项目做到不用我审代码也能上线

之后你只需要读报告、做决定（"可以""先不做""先做第 2 条"），看不懂就说"用更简单的话再说一遍"。

## 它做不到什么

- **只管"写法对不对"，不管"做的事对不对"**：你的产品应该怎么表现，需要你在功能地图里用大白话告诉它
- **有些功能很难自动验证**：需要真实付款的功能、手机 App、硬件，以及"好不好看"这类主观感受。这些功能所在的区域不能免审上线
- **老项目不会一次变干净**：新代码先管住，旧代码慢慢清。免审上线也是一个区域一个区域地开
- **大项目 AI 读不全**：体检只能覆盖重点部分
- **不负责安全和合规审查**：碰钱、权限、用户数据的改动永远要你批准，就是这个原因
- **部分设置要你自己点**：保护主线、指定审批人等平台设置，AI 没权限时会一步一步教你操作
- **会消耗 AI 用量**：验证本来就是用费用换质量
- **AI 要有自己的账号**：GitHub 不允许 PR 作者批准自己的 PR，管理员又能拆掉所有关卡。所以 AI 必须用一个只有写权限的独立账号，用你本人的账号就做不到免审上线
- **私有仓库的上线审批要付费套餐**：GitHub 免费账号只有公开仓库能给部署环境设审批人，私有仓库要 Pro 或 Team
- **风险判断会误报，也可能漏报**：靠关键词判断"碰不碰钱"，误报会让你多批一次；项目自己起的怪名字可能漏掉，所以要把这些名字登记进配置
- **刚开始不会自动上线**：新区域要先攒二十多次没出事的上线记录
- **不是安全审查**：密钥扫描和依赖检查只能拦已知问题。处理隐私、支付的项目仍需专业审查
- **目前只在假项目上测过**：脚本和 4 个评测场景都只在假项目上跑过（结果见 `codebase-gardener/evals/RESULTS.md`），还没在真实项目上跑完全程

## 思路来源

这个 skill 的核心思路来自 Lauren Tan（[poteto](https://x.com/poteto)，SpaceXSI Grok Bot 团队工程师）的公开分享：

- 演讲 [All Code Is Slop (Except Mine)](https://ai.engineer/talks/O_zcc6Xl12g-all-code-is-slop-except-mine)，AI Engineer Code Summit，2026 年 11 月
- 2026 年 9 月在 X 上发布的视频分享《how i shipped 2,500 PRs last month》

借用的核心观点：

- **倒置信任金字塔**：优先用代码结构和自动检查拦住错误，文字规则和人工审查放在最后
- **每次纠正都变成确定性的检查**，而不是在 AGENTS.md 里多加一行
- **代码库就是 AI 的记忆**：坏写法会被照抄，所以要清理旧的坏样板
- **用证据验证**：让 AI 自己运行应用，截图、测试；用"功能地图"让 AI 知道有哪些功能、怎么试
- **先打牢基础，再谈自动化**："内层循环产出垃圾，自动化只会产出更多垃圾"

检查标准里的通用信号和验证要求，来自她公开的 pstack 原则（[cursor/plugins](https://github.com/cursor/plugins) 仓库中的 `principle-fix-root-causes`、`principle-prove-it-works`，MIT 许可）。

上线流水线和风险分级参照了这些公开资料：

- GitHub 文档 [About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)：检查不过不能合并（阶段 6a）
- GitHub 文档 [About code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)：指定文件的改动必须由指定的人批准（阶段 7 的红色区域）
- Google SRE Workbook [Canarying Releases](https://sre.google/workbook/canarying-releases/)：先小范围上线、对比、异常就退回（阶段 6c）
- Google 论文 [State of Mutation Testing at Google](https://research.google/pubs/state-of-mutation-testing-at-google/)，以及变异测试工具 [Stryker](https://stryker-mutator.io/)、[mutmut](https://github.com/boxed/mutmut)、[PIT](https://pitest.org/)：自动注入错误，量测试能抓住多少（埋雷测试）
- Google SRE Book [Postmortem Culture](https://sre.google/sre-book/postmortem-culture/)：出事后记录原因和补救、不追究个人（事后追账）
- [DORA 交付指标](https://dora.dev/guides/dora-metrics-four-keys/)：变更失败率、恢复时间（放权的依据）
- Google SRE Workbook [Error Budget Policy](https://sre.google/workbook/error-budget-policy/)：错误预算用完就停止上线
- [Rule of three](https://en.wikipedia.org/wiki/Rule_of_three_(statistics)) 和 [Wilson 区间](https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval#Wilson_score_interval)：样本少时估计失败率的上界
- [Kayenta 自动金丝雀分析](https://cloud.google.com/blog/products/devops-sre/how-to-use-kayenta-for-automated-canary-analysis)：拿新旧版本同时段的指标对比
- Martin Fowler [Feature Toggles](https://martinfowler.com/articles/feature-toggles.html) 和 [Parallel Change](https://martinfowler.com/bliki/ParallelChange.html)：功能开关；数据库分步改结构
- Google Testing Blog [Test Flakiness](https://testing.googleblog.com/2020/12/test-flakiness-one-of-main-challenges.html)：时好时坏的测试
- [SLSA](https://slsa.dev/)、[OWASP Top 10](https://owasp.org/www-project-top-ten/)、[gitleaks](https://github.com/gitleaks/gitleaks)：供应链、常见安全问题、密钥扫描
- GitHub 文档 [Managing environments for deployment](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-deployments/managing-environments-for-deployment)：上线前的人工审批
- Anthropic [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)：skill 的写法和长度

面向非程序员的部分（大白话汇报、只读诊断、逐条批准、关卡演示、五项前提评分、按风险分级放权、功能雷和达标线、漏网暂停规则、各本账本）是本 skill 自己加的。

**哪些数字是自定的**：变更失败率上界 15%、恢复中位时间 60 分钟、埋雷最长间隔 35 天、雷至少两种来源、证据有效期 90 天、每个核心功能 1 到 3 个雷，都是本 skill 定的起步值，没有行业统一标准。95% 置信度是统计学惯例。跑满三个月后应该用实测数据重新定。

本项目是对公开演讲内容的个人整理和改编，与 Lauren Tan 本人、SpaceXSI、GitHub、Google、DORA 都没有关联。

## License

MIT
