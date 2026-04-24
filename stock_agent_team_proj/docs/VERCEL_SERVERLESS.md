# Vercel Serverless 与长耗时分析

## 当前限制

[vercel.json](../vercel.json) 将 `api/index.py` 的 `maxDuration` 设为 **60 秒**（Vercel 上可调上限受套餐约束）。而一次完整的 **LLM 多轮讨论 + 规则引擎** 可能超过 60 秒，存在超时与连接中断风险。

## 推荐部署形态

1. **静态前端 + 自建 API**（推荐）  
   - 在 Vercel/Netlify 等仅部署 `web/static` 的静态资源，将 `API_BASE` 指到自建主机（如带 FastAPI 的 VPS、云函数不受 60s 限制的环境）。  
   - 长连接 SSE 由具备合适超时与读超时的反向代理（Nginx/ Caddy）承载。

2. **全栈同一进程**（开发/小流量）  
   - 本机或单机 Docker：`uvicorn web.app:app`，无 60s 切分，适合 [LOCAL_DEPLOYMENT.md](./LOCAL_DEPLOYMENT.md) 所述流程。

3. **若必须全托管在 Vercel**  
   - 将 LLM 分析改为 **异步任务**：客户端 `POST` 创建任务，返回 `task_id`；由后台 Worker 执行分析，前端轮询 `GET /api/tasks/{id}` 或使用 WebSocket/第三方队列。  
   - 或缩短链路：仅部署规则引擎 `POST /api/analyze`，LLM 模式不在 Serverless 上提供。

4. **文档与配置**  
   - 在环境变量中区分 `PUBLIC_API_URL`，前端构建时注入，避免生产仍指向 `localhost:8000`。

## 与仓库入口的对应关系

- 根目录 [api/index.py](../api/index.py) 为 Serverless 适配入口；与 `web.app` 行为应对齐并保持依赖可在冷启动内加载。  
- 本文件为架构说明，**不修改运行时默认值**；若你延长 `maxDuration`，请在 Vercel 控制台与 `vercel.json` 中同步调整。
