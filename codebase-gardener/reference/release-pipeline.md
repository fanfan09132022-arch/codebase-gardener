# 上线流水线：怎么搭（阶段 6 和 7 的细节）

## 目录
- 先决条件：AI 必须用独立账号
- 本机发版的项目
- 装哪些文件
- 主线保护和部署环境：使用者要点的设置
- 6a 强制关卡
- 6b 自动验证，以及时好时坏的测试
- 6c 小步上线、金丝雀、自动退回
- 功能开关
- 数据库和数据迁移
- 安全检查
- 还剩下的风险

## 先决条件：AI 必须用独立账号

「AI 不能放松自己的关卡」只靠 AI 自觉是不够的，要靠权限做到。

- AI 用一个单独的 GitHub 账号或 GitHub App 提交代码、开 PR。这个账号只有「写」权限，没有「管理员」权限。
- 理由一：GitHub 不允许 PR 作者批准自己的 PR。AI 如果用使用者的账号提 PR，使用者就批不了，红色改动的审批会失效。
- 理由二：有管理员权限就能改主线保护、改仓库变量、改部署环境的审批人，等于能拆掉所有关卡。
- 使用者本机如果让 AI 直接用自己登录的 `gh` 或 git 凭据，以上两点都不成立。阶段 6 开始前必须换掉。
- 达标证据：在 `docs/守门规则.md` 记下 AI 账号名、它的权限级别，以及一次演示：用 AI 账号去改主线保护，被拒绝。

做不到这一条的项目，前提 2「强制关卡」最多 🟡，不能进入阶段 7。

## 本机发版的项目

有些项目不走「GitHub 合并后自动上线」，而是在本机用一个发版脚本，把某个提交复制到发布目录再切换过去，常见的还会从多个分支发版。这时 GitHub 工作流模板用不上，按下面做：

- **关卡接进现有发版脚本**，不另起一套。脚本在切换前依次跑：`risk_scan.py --base <线上版本的提交>` 判风险；这次改动涉及区域的 `gate_command`；`release_gate.py check`。任何一步不通过就不切换。切换后跑健康检查，再 `release_gate.py record`。改发版脚本本身是红色改动。
- **账本从已有记录导入。** 发版脚本已经按行记录每次上线和退回的，用 `release_gate.py import-history` 一次导入，之后由发版脚本调用 `record` 追加。导入的退回会让区域处于暂停，使用者确认那些问题已处理后再 `resume`。
- **返工另算上限。** 导入只看得到「退回」，看不到「发出去以后又发一版来修」。按提交信息里 fix、hotfix 的比例估一个上限，汇报时和退回率一起给，不只报低的那个。
- **按区域定关卡。** 完整测试套件跑太久（超过几分钟）的，在区域配置里写自己的 `gate_command`，只跑这个区域相关的测试。区域关卡必须先用这个区域的历史雷验证过：拦下率达到要求才算数。
- **局限要照实写。** 本机关卡和 AI 用的是同一台机器、同一套权限，AI 改发版脚本或直接切换发布目录就能绕过。所以前提 2 最多 🟡，阶段 7 只能放权到「使用者看证据摘要后一键批准」，不能完全免审，除非换到 AI 没有权限的机器或服务上发版。
- 私有仓库加 GitHub 免费账号时，主线保护和部署环境审批都开不了（API 返回 403），也会落到这一节。

## 装哪些文件

skill 目录里的文件复制到项目，复制本身是红色改动，要使用者批准：

| skill 里的文件 | 放到项目哪里 | 作用 |
|---|---|---|
| `scripts/risk_scan.py` | `.gardener/bin/` | 判断改动的风险等级 |
| `scripts/release_gate.py` | `.gardener/bin/` | 判断区域能不能自动上线，记上线账本 |
| `scripts/run_mines.py` | `.gardener/bin/` | 埋雷测试 |
| `scripts/health_check.py` | `.gardener/bin/` | 上线后健康检查 |
| `scripts/ledger.sh` | `.gardener/bin/` | 取出和保存上线账本分支 |
| `templates/gardener-config.json` | `.gardener/config.json` | 区域、风险等级、阈值 |
| `templates/github/gardener-ci.yml` | `.github/workflows/` | 合并前关卡 |
| `templates/github/gardener-release.yml` | `.github/workflows/` | 上线流水线 |
| `templates/github/gardener-ledger.yml` | `.github/workflows/` | 每月埋雷、登记问题、恢复区域 |
| `templates/github/CODEOWNERS` | `.github/CODEOWNERS` | 按路径指定审批人 |
| `templates/docs-*.md` | `docs/` | 使用者看的账本 |

脚本只用 Python 3.8 以上的标准库，不用装别的包。项目不用 GitHub 时，脚本照样能用，工作流要按所用平台改写，主线保护和审批人设置要找到对应功能。

## 主线保护和部署环境：使用者要点的设置

AI 没有权限改这些设置，要一步一步教使用者点。点完后由 AI 做演示确认生效。

主线保护，在 Settings > Branches 或 Rules 里：
- 合并前必须开 PR，不能直接推主线。
- 必须通过的检查：`checks`、`security`、`risk`。
- 勾选「Require review from Code Owners」。
- 勾选「Do not allow bypassing」，管理员也不例外。
- 新提交推上来后，旧的批准作废。

部署环境，在 Settings > Environments 里：
- `production-auto`：不设审批人。
- `production`：审批人只填使用者本人。不要勾「Prevent self-review」，否则使用者自己合并的改动就没人能批。
- 免费账号只有公开仓库能用部署环境的审批和主线保护；私有仓库要 GitHub Pro 或 Team。见 [GitHub 文档](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-deployments/managing-environments-for-deployment)。

仓库变量，在 Settings > Secrets and variables > Actions > Variables 里：
- `GARDENER_OWNER`：使用者的 GitHub 用户名。
- `GARDENER_PROD_URL`：正式环境地址。

## 6a 强制关卡

- `gardener-ci.yml` 的三个任务：`checks` 跑全部检查和测试，`security` 查密钥和依赖漏洞，`risk` 判断风险等级。
- 关卡命令、风险脚本和配置都从**主线**读，不从这次改动读。否则一次改动可以顺手把关卡命令改成什么都不查，或把风险脚本改成永远判绿。
- 红色改动要使用者批准**当前最新提交**。批准之后 AI 又推了新提交，批准自动作废。
- 演示：开一个故意让测试失败的 PR，看它合不进去；开一个改 `.gardener/config.json` 的 PR，看它要求使用者批准。

## 6b 自动验证，以及时好时坏的测试

- 按功能地图，给每个核心功能写自动验证，全部接进 `gate_command`。
- 功能地图要和代码对账：列出代码里所有入口（页面、接口、命令行命令、定时任务、消息处理），和地图逐条对。对不上的写进功能地图的「对账」表，等使用者决定。这一步用来弥补「使用者看不出地图漏了什么」。
- **时好时坏的测试**（同一版本代码，有时过有时不过）会毁掉关卡：大家会习惯性重跑，直到碰巧通过。规则：
  - 关卡不许自动重试到通过为止。
  - 发现一个时好时坏的测试，就记进 `docs/守门规则.md` 的隔离清单，并当天修。修好前，它覆盖的功能算「没有自动验证」，所在区域前提 3 降为 🟡。
  - 先怀疑测试本身，比如依赖时间、顺序、网络、共享状态，再怀疑被测代码。
- 搭好后跑第一次埋雷测试，见 `reference/measurement.md`。

## 6c 小步上线、金丝雀、自动退回

- 每次上线留版本号。`rollback.sh` 能把正式环境退回上一个正常版本。
- 上线后跑 `health_check.py`。不通过就自动执行 `rollback.sh`，记账，区域暂停。
- **金丝雀**：能先发给一小部分用户就先发，观察一段时间再全量。只看「页面能打开」不够。有监控时，要拿新版本的错误率、延迟和旧版本**同时段**对比，明显变差就退回。参照 Google SRE 的[金丝雀发布](https://sre.google/workbook/canarying-releases/)和 [Kayenta 自动金丝雀分析](https://cloud.google.com/blog/products/devops-sre/how-to-use-kayenta-for-automated-canary-analysis)。
- 没有监控的项目，至少把错误日志的数量接进健康检查。完全没有上线后观测手段的区域，前提 4 最多 🟡。
- 演示：在测试环境上线一个故意带问题的版本，看它被自动退回，账本里多一条记录，区域变成暂停。

## 功能开关

中风险改动尽量放在功能开关后面上线。参照 Martin Fowler 的 [Feature Toggles](https://martinfowler.com/articles/feature-toggles.html)。

- 代码先上线，开关默认关；再对一小部分用户打开；没问题再全开。
- 关开关比退回整个版本快，是最快的「撤销键」。
- 每个开关登记负责人和到期日。到期不清理的开关会变成新的坏样板。
- 打开或关闭碰钱、权限的开关，按红色处理。

## 数据库和数据迁移

退回代码救不回已经改坏的数据。所以迁移永远是红色，并且要分步做，每一步都能单独退回。参照 [Parallel Change](https://martinfowler.com/bliki/ParallelChange.html)：

1. **加**：只新增字段或表，不删不改旧的。新旧代码都能跑。
2. **双写和搬数据**：新代码同时写新旧两处，后台把旧数据搬过去，搬完核对数量和抽样。
3. **切读**：代码改成读新的。
4. **删**：确认一段时间没问题，再删旧字段。这一步单独一次上线，单独批准。

每次迁移前先备份，并在测试环境演练过一次「从备份恢复」。没演练过恢复的项目，碰数据的区域前提 4 不能算 ✅。

## 安全检查

`security` 任务做三件事：查代码里有没有写进密钥，查依赖里已知的漏洞，以及在公开仓库可以打开 GitHub 自带的 CodeQL 和 Dependabot。

另外：
- 工作流里引用的 Action 按提交哈希锁定版本，不用会变的标签。参照 [SLSA](https://slsa.dev/) 的供应链要求。
- 依赖要有锁定文件，例如 `package-lock.json`、`poetry.lock`。
- 碰登录、权限、用户输入的代码，对照 [OWASP Top 10](https://owasp.org/www-project-top-ten/) 检查。这类区域本来就是红色，AI 在证据摘要里要写明查了哪几条。
- 这些检查只能拦已知问题，不等于安全审查。处理用户隐私、支付的项目仍需要专业的安全审查。

## 还剩下的风险

说清楚这套机制管不到的地方，写进 `docs/上线就绪.md` 的末尾：

- **账本分支**：流水线有权写，有仓库写权限的账号理论上也能写。每月跑一次 `bash .gardener/bin/ledger.sh audit`，账本提交的作者应该只有流水线机器人。
- **关键词判断**：会误报，也会漏报。漏报的主要来源是项目自己的命名，所以阶段 1 要把项目里碰钱、权限的函数名写进 `red_keywords_extra`。
- **功能地图**：AI 的对账只能找出「代码有、地图没有」的入口，找不出「地图写错了」。这部分只能靠事后追账逐步修正。
- **非代码的故障**：服务器、第三方服务、配置。流水线只管代码改动。
