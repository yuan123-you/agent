# 横向溢出浏览器回归检查

1. 使用满足项目要求的 Node.js（>= 22.22.2）运行 `npm run dev -- --host 127.0.0.1`。
2. 在真实浏览器打开 `http://127.0.0.1:5173/tests/layout.html`。
3. 等待结果中的 `done` 与 `total` 相等；`failures` 必须为空。

测试通过独立 iframe 在 320、375、768、1280px 下挂载真实路由、布局和页面组件，覆盖 25 个路由及 8 个弹窗/注册状态（共 132 组）。数据包含连续长商品名、订单号、地址、聊天代码块和 Markdown 表格。测试替换 API、SSE 和 iframe 内的认证存储，不请求真实后端，不更改开发者登录状态。

检查根节点、主内容滚动容器和可见后代的 `scrollWidth <= clientWidth + 1`，容忍 1px 的取整误差。表格/选项卡的内部滚动、轮播动画和步骤连接线不单独判失败，但它们的父级内容区域仍必须满足宽度检查；不能靠根节点裁切来通过测试。

可定点复测，例如：`http://127.0.0.1:5173/tests/layout.html?route=/products/1&width=375`。

此入口仅用于 Vite 开发服务器，不参与生产构建。

## 加载状态视觉回归

在开发服务器打开 `/tests/loading.html?variant=detail` 检查真实 LoadingState 组件。
`variant` 支持 `detail`、`cards`、`list`、`table`、`stats`、`text`、`spinner`；加 `&dark` 检查暗色主题。
在 320/390px 与 1440px 宽度核对无横向溢出；`spinner` 应在视口正中心。
`?variant=spinner&dialog` 在真实 Element Plus 对话框内复测视口居中。
启用系统“减少动态效果”后，骨架渐变和加载旋转均应停用。
此独立入口没有 API 请求，不读取或修改登录状态，也不参与生产构建。
