# 安全说明

## 密钥处理

- `pixiv_通行密钥.json`、`refresh_token`、`settings.json` 只应保存在本机，不要提交到仓库、Issue、截图或聊天记录。
- 本程序只在 `127.0.0.1` 上监听，本地 API 带一次性 Token 和 Host/Origin 校验。
- 如果怀疑密钥泄露，请立刻在 Pixiv 账号设置中撤销会话并重新登录，然后更新本地密钥文件。

## 报告安全问题

请优先使用 GitHub 仓库的 **Private vulnerability reporting**（Security → Report a vulnerability）提交，不要在公开 Issue 中粘贴密钥、token、代理密码或完整日志。

提交时请提供：

- 受影响版本/commit；
- 复现步骤；
- 不包含密钥的最小日志或截图；
- 你希望如何署名。

## 不在范围内

- 因违反 Pixiv 服务条款导致的账号问题；
- 下载内容的版权问题；
- 用户自行修改代码或第三方插件导致的问题。
