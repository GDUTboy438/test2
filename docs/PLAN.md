# Web 主界面深色版联动与服务层对接实施计划

## 摘要
- 目标：基于 `docs/webui.pen` 的深色侧栏方案（`PVM Home Rebuild - UX Max Variant`），完成 Web 主页面像素级还原与服务层联动。
- 本轮只做 Web 端：改 `web/` + 必要 `app/web_api.py`，不维护 `app/ui` 桌面端。
- 策略：阶段化混合。先用最小后端增量完成上线，再为后续“设置子 UI（开始扫描/日志）”预留扩展位。

## 范围与非范围
- 范围内：
1. 目录树联动（两级：根库节点 + 一级子目录）。
2. 全库搜索（300ms 防抖）。
3. 列表/网格双视图联动。
4. 筛选（状态、分辨率）与排序（名称/修改时间/时长/大小 + 升降序）。
5. 分页（每页 20，页码 + 上一页/下一页）。
6. 右侧详情栏 + 播放按钮真实可用。
7. 深色侧栏视觉还原（含 `Fira Sans` 在线字体）。
- 范围外：
1. 开始扫描、扫描日志入口改造（后续放到设置子 UI）。
2. 标签管理功能实现（本轮按钮禁用）。
3. 手机端完整适配（仅保证电脑浏览器体验）。

## 公共接口与类型变更
1. 后端新增 `GET /api/library/current`（`app/web_api.py`）。
返回：`{ ok, data: { name, root }, error }`。
无库时：`NO_LIBRARY`。
2. 后端增强 `GET /api/entries`（`app/web_api.py`）。
新增查询参数：`recursive: bool = false`。
`recursive=true & path=""` 返回全库视频。
`recursive=true & path="x"` 返回该目录子树内视频。
3. 后端新增 `POST /api/entries/open`（`app/web_api.py`）。
请求：`{ path: string }`（视频相对路径）。
行为：调用 `service.open_entry(path)`，由系统默认播放器打开。
4. 前端类型更新（`web/src/types.ts`）。
新增：`LibraryInfo`、`DirectoryTreeNode`、`ViewMode`、`SortField`、`SortDirection`、`FilterState`、`PaginationState`、`ToastState`。
5. 前端服务层更新（`web/src/services/library.ts`）。
新增：`getCurrentLibrary()`、`openEntry(path)`。
增强：`getVideos({ path, recursive })`、`getDirectoryGroups` 改为目录树接口。

## 详细实施步骤（决策完备）
1. API 层改造（`app/web_api.py`）。
实现 `library/current`、`entries/open`、`entries(recursive)`。
统一沿用现有 `ok/fail` 响应结构和错误码风格。
2. 前端数据层改造（`web/src/services/library.ts`, `web/src/services/api.ts`, `web/src/types.ts`）。
将“目录、视频、搜索、播放、库信息”封装为统一服务函数。
保留 `VITE_USE_MOCK` 兼容，但新增接口也提供 mock 回退。
3. 应用状态重构（`web/src/App.tsx`）。
状态包含：库信息、当前目录、搜索词、防抖搜索词、筛选、排序、分页、视图模式、选中视频、提示消息。
加载流程：
启动先调 `getCurrentLibrary`。
有库则加载目录树和默认数据（根节点=全库）。
目录变化/搜索变化按规则拉取基数据。
筛选排序分页在前端派生。
4. 目录树与面包屑（`web/src/components/layout/Sidebar.tsx`, `web/src/components/layout/BreadcrumbRow.tsx`）。
左侧第一层固定为“媒体库根节点”（显示末级目录名，tooltip 显示全路径）。
仅加载两级结构。
点击根节点显示全库文件。
面包屑实时显示“库名 / 当前目录”。
5. 列表与网格视图（`web/src/components/layout/FileTable.tsx`，新增 `web/src/components/layout/FileGrid.tsx`）。
列表模式显示表头。
网格模式隐藏列表表头，仅显示卡片网格。
两个视图共享同一份已筛选/已排序/已分页数据。
6. 筛选、排序、分页（`web/src/components/layout/SubBar.tsx`，新增 `web/src/components/layout/PaginationBar.tsx`）。
筛选器：按钮下拉面板，多选状态和分辨率。
排序器：双区按钮。
左侧箭头切换升降序。
右侧下拉选择排序字段，切字段时保留当前升降序。
默认排序：修改时间倒序。
分页：每页 20，页码+上一页/下一页。
目录/搜索/筛选变化时重置到第 1 页。
7. 详情与播放（`web/src/components/layout/DetailPanel.tsx`, `web/src/App.tsx`）。
保留右侧详情栏形态。
播放按钮调用 `openEntry`。
成功/失败通过状态栏轻提示反馈。
8. 视觉还原（`web/src/index.css`, `web/tailwind.config.js`, 各 layout 组件）。
引入 `Fira Sans`（Google Fonts）。
按 `webui.pen` 深色侧栏方案统一颜色、圆角、字重、间距。
`标签管理`按钮设为禁用态。
`Stop Scan` 保持展示但本轮禁用，避免与后续设置子 UI 冲突。

## 关键交互规则
1. 搜索规则：输入即搜（300ms），有关键词时全库搜索优先，清空后恢复当前目录数据源。
2. 过滤规则：状态组 OR、分辨率组 OR、组间 AND。
3. 排序规则：先字段后方向统一比较；名称用 `Intl.Collator("zh-Hans-CN", { numeric: true })`。
4. 选择规则：数据源变化后若选中视频不在当前页，自动清空详情栏选中态。
5. 失败处理：所有接口失败都落到状态栏轻提示，不用阻塞式 alert。

## 测试用例与验收场景
1. API 合约验证。
`GET /api/library/current`：有库/无库两种返回正确。
`GET /api/entries?recursive=true`：全库返回数量 >= 非递归返回。
`POST /api/entries/open`：有效路径返回成功，非法路径返回 `NOT_FOUND`。
2. UI 联动验证。
选择目录库后左侧出现“根节点+一级子目录”。
点击根节点显示全库数据。
点击子目录显示该目录数据。
3. 搜索验证。
输入关键词后结果跨目录。
清空关键词后恢复目录视图。
4. 筛选排序验证。
状态与分辨率组合筛选正确。
排序字段切换不改变升降序状态。
左侧箭头切换立即重排。
5. 视图与分页验证。
列表/网格切换保持当前筛选排序分页。
网格模式不显示列表表头。
分页固定 20 条。
切换目录/筛选/搜索回到第 1 页。
6. 详情与播放验证。
选中行打开右侧详情。
点击播放可拉起系统播放器。
失败提示显示在状态栏。
7. 构建验证。
运行 `web` 的 `npm run build` 必须通过。

## 风险与缓解
1. 全库数据量大导致前端排序筛选开销上升。
缓解：保留后端查询增强扩展位，下一阶段可把排序筛选下推到 API。
2. 本地打开文件在不同系统行为差异。
缓解：统一通过后端 `open_entry`，前端只负责提示与重试。
3. 深色主题像素还原与动态数据冲突。
缓解：先固化 token 与布局，再做数据联动，最后统一视觉回归。

## 默认假设与已锁定决策
1. 仅电脑浏览器为目标端。
2. 本轮不实现开始扫描和日志入口交互。
3. 标签管理按钮禁用。
4. 详情采用右侧栏，不改弹窗/独立路由。
5. 字体使用 Google Fonts 在线加载 `Fira Sans`。
6. 分页固定 20 条。
7. 搜索全库优先。
8. 根节点点击显示全库。
9. 两级目录结构中第一层是媒体库路径节点。
