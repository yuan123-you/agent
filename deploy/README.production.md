# AI Mall Oracle 部署与运维

部署日期：2026-10-08。服务器：Oracle，Ubuntu ARM64。

## 入口
- 主域名：https://aimall.novo.ccwu.cc/ （跳转 /aimall/）
- 按本人要求仅提供域名入口，不提供或展示 IP 备用地址。
- 这是项目演示环境，不提供真实交易、扣款和发货；不要输入真实敏感信息。
- 当前桌面网络对 .ccwu.cc 域名的 TLS 连接曾出现重置；域名源站正常。按本人要求撤销 IP 备用路由，不以公开源站 IP 解决可达性问题。
- Cloudflare Browser Integrity Check 会拒绝默认 Python User-Agent（1010）；域名链路用 curl 验证。功能验收通过私有回环代理执行，域名页面和商品数据另行通过 HTTPS 验证。

## 文件、密钥与服务
- 代码：/srv/aimall/repo，基于远程提交 796c4ee03dea598db758a8d3082349537654d693，再应用本次本地生产补丁。
- 生产编排：/srv/aimall/repo/deploy/compose.production.yml。
- 密钥：/srv/aimall/secrets/production.env（目录 700，文件 600，不入 Git）。
- 管理员：admin；随机密码仅通过私密 admin-access.txt 交付，不在日志或公开页面展示。
- 仅前端 127.0.0.1:18100 映射宿主机；数据库、Redis、对象存储、向量库、模型和 AI 接口只在独立 Docker 网络中使用。
- 使用非 root MySQL 应用账号、随机 JWT/内部令牌/存储凭据、来源白名单、登录/注册限流及 AI 消息限流。
- 前端、后台、数据和模型目录持久化，容器自动重启；部署必须等待健康检查通过。
- 九个服务：mysql、redis、minio、milvus、ollama、embeddings、ai-service、backend、frontend。

## AI 配置
- 对话：Ollama 0.40.1 + qwen3.5:4b，关闭扩展思考，CPU 运行。
- 向量：独立 Ollama 进程 + qwen3-embedding:0.6b，1024 维，单 CPU，避免初始化影响对话。
- 新向量集合 kb_chunks_qwen3_embedding_06b_1024 / product_index_qwen3_embedding_06b_1024，不混用不同模型的向量。
- 商品索引每小时同步；大批量知识库初始化、重排序及 Langfuse 默认关闭。没有复制本机云 API 密钥或开启新付费模型。
- CPU 对话仍可能需要数十秒；这不是 GPU 推理部署，也不承诺高并发即时响应。

## 安全维护边界
- 前端生产依赖安全检查已修复兼容范围内问题；PDF 解析 pypdf 升至 6.19.0。
- setuptools<81 仍因 pymilvus 2.4.15 的 pkg_resources 兼容要求保留。审计命中 PYSEC-2026-3447（重复条目）：macOS APFS/HFS+ 文件名规范化导致 MANIFEST.in 排除规则失效，影响源码包生成；本 Linux 运行容器不生成源码分发包，没有公网构建入口。该依赖并未宣称清零，应随未来 Milvus 客户端升级处理。
- MinIO 原二进制镜像已不可下载，改从官方固定发布标签/提交构建，运行账号非 root，不公开 API 或控制台。
- 此次为生产部署基础加固与相关检查，不是全面渗透测试或零漏洞保证。

## HTTPS
- 域名证书：/etc/letsencrypt/live/aimall.novo.ccwu.cc，当前有效至 2027-01-06。
- certbot.timer 自动续期；新增部署钩子在该证书续期后检查并 reload Nginx。已执行模拟续期验收。
- AI Mall 的 IP 入口已关闭；既有证书与其他项目的服务不在此次调整范围内。
- Nginx 站点：/etc/nginx/sites-available/aimall.novo.ccwu.cc；IP 站点拒绝 aimall 路径；保留其他项目既有服务配置。修改前副本位于 /srv/aimall/backups/。

## 常用命令
```bash
cd /srv/aimall/repo
sudo docker compose --env-file ../secrets/production.env -f deploy/compose.production.yml ps
sudo docker compose --env-file ../secrets/production.env -f deploy/compose.production.yml up -d --wait --wait-timeout 180
sudo docker compose --env-file ../secrets/production.env -f deploy/compose.production.yml logs --tail 100 backend ai-service
python3 deploy/test_production.py
python3 deploy/smoke-test.py
sudo nginx -t
sudo certbot renew --cert-name aimall.novo.ccwu.cc --dry-run --no-random-sleep-on-renew
```

更新代码时先检查 git status：服务器应用了未推送的本地部署补丁，不可直接 reset/clean。先备份数据和补丁，再 review 拉取差异、构建并等待健康状态。不要执行 docker compose down -v。

## 手动数据备份示例
只读导出，不删除原卷。备份目录应仅管理员可读；数据库与对象存储应一起备份。
```bash
cd /srv/aimall/repo
sudo install -d -m 700 /srv/aimall/data-backups
sudo docker compose --env-file ../secrets/production.env -f deploy/compose.production.yml exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction --routines --triggers ai_mall' | sudo tee /srv/aimall/data-backups/ai-mall.sql >/dev/null
sudo chmod 600 /srv/aimall/data-backups/ai-mall.sql
```
该命令是运维说明，本次未创建持续运行的备份任务。

## 回滚
停止 aimall-prod 容器但保留数据卷；恢复 /srv/aimall/backups 中对应的 Nginx 配置，nginx -t 通过后 reload。不要停止其他项目容器或删除既有站点、证书、数据库。

## 2026-10-08 域名-only 调整
主页所有项目均只使用各自域名，AI Mall 不再提供 IP 备用入口。部署脚本安装显式 404 拒绝规则，防止回滚更新时重新启用备用服务；CORS 仅允许 AI Mall 域名，私密登录文件仅保留域名。移除链接不等于绝对隐藏源站 IP；源站全面限制到 Cloudflare 来源需单独评估现有所有站点，未擅自变更全服务器防火墙。
