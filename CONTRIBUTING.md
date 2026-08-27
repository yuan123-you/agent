# 贡献指南

感谢参与 AI Mall。所有改动应保持简单、可验证，并只解决明确的问题。

## 开发流程

1. 从最新 `main` 创建短生命周期分支，例如 `feature/short-name`、`fix/short-name` 或 `docs/short-name`。
2. 修改前先确认需求和验收条件；Bug 修复先添加可复现测试。
3. 保持改动聚焦，不重构无关代码，不引入未使用的依赖或配置。
4. 提交前运行受影响模块测试；跨模块或发布改动运行完整验证矩阵。
5. 通过 Pull Request 合并，说明动机、行为变化、验证命令和结果。

## 提交规范

使用简洁的 Conventional Commit 风格：

```text
feat: add buyer-approved after-sale action
fix: reject stale knowledge-base vectors
test: cover bm25 metadata filtering
docs: update local deployment guide
chore: ignore local evaluation output
```

一次提交应表达一个可审查的目的。禁止用生成物、格式化或无关清理淹没功能差异。

## 必须验证

```bash
# Backend
cd backend && mvn -B test

# Frontend
cd frontend && npm ci && npm test && npx tsc --noEmit && npm run build

# AI service
cd ai-service && pip install -r requirements.txt -r requirements-dev.txt && pytest -q

# Eval and deterministic data
python -m pytest eval/tests backend/scripts/tests -q

# Docker

docker compose config --quiet
```

只改文档时可以不运行全部应用测试，但必须检查链接、命令和路径确实存在。

## 代码约定

- Java 使用项目现有 Spring Boot/MyBatis-Plus 分层和 Java 17。
- Python 保持类型清晰、异步边界明确；外部服务必须有超时和可测试的降级行为。
- Vue/TypeScript 保持类型检查通过，复用现有 API、Store、Composable 和组件。
- 数据库变更只能新增 Flyway 迁移；不得修改已发布迁移。
- 高风险 Agent 动作必须经过用户确认，不能绕过后端权限和状态校验。
- RAG 回答必须保留来源、当前版本校验和证据不足降级。

## 敏感信息与生成文件

禁止提交：

- `.env`、真实 API Key、Token、私钥、生产域名或数据库凭据；
- `node_modules`、`dist`、`target`、虚拟环境、缓存、日志和 IDE 文件；
- 数据库导出、线上用户数据、未获授权的媒体或抓取内容；
- `.worktrees`、`.superpowers` 等代理/工作区运行产物。

需要提交的生成数据必须满足：生成脚本可重复、来源和许可证允许、报告可审计、测试验证数量与格式。商品目录和知识库生成后应一起提交清单、报告及相关测试。

## Pull Request 检查表

- [ ] 需求与范围明确，没有无关重构。
- [ ] 新行为或 Bug 有自动化测试。
- [ ] 所有相关测试、类型检查和构建通过。
- [ ] README、API 或部署文档已同步。
- [ ] 没有密钥、日志、缓存、临时文件或超大无关文件。
- [ ] 数据库迁移可前向执行，且未修改历史迁移。
- [ ] 高风险业务动作仍要求后端授权和用户确认。
