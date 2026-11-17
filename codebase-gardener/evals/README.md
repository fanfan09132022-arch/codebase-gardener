# 评测

按 Anthropic 的 skill 编写建议，每个评测一个 JSON：`skills`、`query`、`files`、`expected_behavior`。
`fixture/` 是评测用的假项目，说明见 `fixture/README.md`。

怎么跑（手动）：
1. 把 `fixture/` 复制到临时目录，`git init` 并提交一次。
2. 在临时目录里分别用「装了这个 skill」和「没装」各跑一次 `query`。
3. 逐条对 `expected_behavior` 打勾。没装 skill 时的结果就是基线，skill 要明显好于基线才算有用。
4. 换不同模型各跑一次（例如 `claude -p --model claude-haiku-5-5`、`claude-sonnet-5-5`、`claude-opus-5-5`）。

| 评测 | 考什么 |
|---|---|
| 01 | 没有埋雷记录和上线记录时，拒绝开启自动上线 |
| 02 | 未登记目录里的退款代码判为红色 |
| 03 | 拒绝删掉没拦下的雷，改为补测试 |
| 04 | 体检时每条结论都有依据 |

最近一次结果见 `RESULTS.md`。
