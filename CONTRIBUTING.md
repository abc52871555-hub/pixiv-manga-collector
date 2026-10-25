# 贡献指南

感谢你愿意改进这个项目。

## 提交 Issue

- Bug：说明版本、操作系统、复现步骤、期望行为和实际行为。
- 功能建议：说明使用场景，不要只写“加个功能”。
- **不要**在 Issue 中粘贴 refresh_token、密钥文件、代理密码或完整的私人日志。

## 提交 Pull Request

1. Fork 本仓库；
2. 从 `main` 创建分支，例如 `feature/related-scan` 或 `fix/token-extract`；
3. 保持改动聚焦，不要顺手格式化整个文件；
4. 提交前运行：

   ```bash
   python -m py_compile server.py metadata_inspect.py token_login.py
   node --check web/app.js
   ```

5. 在 PR 描述里写清楚改了什么、怎么验证；
6. 不要提交 `output/`、`logs/`、`settings.json`、`pixiv_通行密钥.json` 或真实作品图片。

## 代码风格

- Python 保持现有单文件结构，函数尽量小而明确；
- 前端不引入构建工具，保持原生 HTML/CSS/JS；
- 面向用户的文案使用中文；
- 新增网络请求必须考虑超时、失败重试和代理设置。

## 许可证

提交 PR 即表示你同意你的贡献以本项目的 MIT 许可证发布。
