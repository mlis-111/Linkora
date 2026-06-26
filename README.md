# Linkora — 校园即时通信与文件传输系统

> 基于 Python + PyQt5 的校园即时通信桌面应用，支持私聊/群聊、好友管理、端到端加密文件传输与 AI 智能问答。

## 📑 目录

- [项目简介](#项目简介)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [通信协议](#通信协议)
- [加密方案](#加密方案)
- [数据库设计](#数据库设计)
- [项目结构](#项目结构)
- [测试](#测试)
- [开发团队](#开发团队)
- [许可证](#许可证)

---

## 项目简介

**Linkora**（校园即时通信系统）是一个功能完善的桌面端即时通信平台，模拟微信/QQ 等主流 IM 应用的核心体验，专为校园场景设计。

系统采用 **客户端-服务器** 架构，基于 TCP 长连接与自定义 JSON 协议通信，支持多用户同时在线。聊天消息采用 AES-CBC 端到端加密，保障通信安全。内置 AI 助手模块，通过 DeepSeek API 提供流式智能问答服务。

### 应用场景

- 校园内部即时通信（学生之间、师生之间）
- 课程群组讨论与文件共享
- AI 辅助学习问答（支持上传代码/文档分析）
- 计算机网络课程设计参考实现

---

## 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                       Client (PyQt5)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │  Login   │ │  Chat    │ │  Friend  │ │  AI Panel    │ │
│  │  Window  │ │  Panel   │ │  Panel   │ │  (Markdown)  │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘ │
│       │             │            │               │         │
│  ┌────┴─────────────┴────────────┴───────────────┴───────┐ │
│  │              NetworkClient (TCP + Signal)              │ │
│  └────────────────────────┬──────────────────────────────┘ │
└───────────────────────────┼────────────────────────────────┘
                            │  TCP :9000
                            │  4-byte length + JSON
                            │  AES-CBC encrypted payload
┌───────────────────────────┼────────────────────────────────┐
│                       Server (Python)                       │
│  ┌────────────────────────┴──────────────────────────────┐ │
│  │                  ChatServer (accept loop)              │ │
│  └────────────────────────┬──────────────────────────────┘ │
│  ┌────────────────────────┴──────────────────────────────┐ │
│  │            ClientHandler (per-connection thread)       │ │
│  └────────────────────────┬──────────────────────────────┘ │
│  ┌────────────────────────┴──────────────────────────────┐ │
│  │                 MessageRouter (dispatch)               │ │
│  └──┬────────┬────────┬────────┬────────┬────────┬───────┘ │
│     │        │        │        │        │        │          │
│  ┌──┴──┐ ┌──┴──┐ ┌──┴──┐ ┌──┴──┐ ┌──┴──┐ ┌──┴────────┐  │
│  │User │ │Chat │ │Friend│ │Group│ │File │ │ AI (Deep- │  │
│  │     │ │     │ │      │ │     │ │     │ │ Seek API) │  │
│  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └─────┬──────┘  │
│     │       │       │       │       │          │           │
│  ┌──┴───────┴───────┴───────┴───────┴──────────┴───────┐  │
│  │                DB Connection Pool (DBUtils)           │  │
│  └────────────────────────┬──────────────────────────────┘  │
└───────────────────────────┼─────────────────────────────────┘
                            │
                    ┌───────┴───────┐
                    │  MySQL 8.0+   │
                    │  campus_im    │
                    └───────────────┘
```

### 数据流概要

1. **客户端**通过 TCP 连接到服务器端口 9000
2. **服务器**为每个连接创建独立线程 (`ClientHandler`)，负责接收/发送消息
3. 消息格式为 **4 字节大端长度前缀 + UTF-8 JSON 体**
4. 服务器 `MessageRouter` 根据 `type` 字段分发到业务模块处理
5. 聊天消息经 **AES-CBC** 加密传输，服务器解密后以明文存储，转发时重新加密
6. **AI 模块**通过 HTTP 调用 DeepSeek API，以 SSE 流式返回，服务器逐块推送给客户端

---

## 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| **语言** | Python 3.10 | 主要开发语言 |
| **UI 框架** | PyQt5 | 跨平台桌面 GUI |
| **网络通信** | TCP Socket + 多线程 | 长连接，每连接一线程 |
| **数据库** | MySQL 8.0+ | 关系型数据持久化 |
| **数据库驱动** | pymysql + DBUtils | 连接池管理 |
| **加密** | pycryptodome (AES-CBC) | 端到端消息加密 |
| **AI 接口** | DeepSeek API (OpenAI 兼容) | 流式问答、Markdown 渲染 |
| **测试** | pytest + pytest-cov | 单元/集成/系统测试 |
| **包管理** | pip + conda | 环境隔离 |

### 依赖清单

```
pymysql          # MySQL 数据库驱动
DBUtils          # 数据库连接池
PyQt5            # 桌面 GUI 框架
pycryptodome     # AES 加密库
requests         # HTTP 客户端 (AI API 调用)
pytest           # 测试框架
pytest-cov       # 测试覆盖率
```

---

## 功能特性

### 🔐 用户认证

- 用户注册（用户名、昵称、密码）
- 密码安全存储：SHA256 + 随机盐值，兼容旧数据 MD5
- "记住我" 自动登录（`QSettings` 本地持久化）
- 重复登录检测与踢出
- 在线/离线状态全服实时广播

### 💬 即时通信

- **私聊**：一对一 AES 端到端加密聊天
- **群聊**：多人群组聊天，支持群内 @提醒
- **公共聊天室**：全服可见的公共频道
- **离线消息**：接收方离线时提示发送失败
- **历史记录**：永久持久化，支持按会话查询
- **历史删除**：支持删除聊天历史记录
- 消息气泡 UI（渐变蓝色己方 / 白色对方）
- 联系人列表（在线状态绿点、未读计数、会话预览）

### 👥 好友管理

- 好友搜索（按 ID / 用户名 / 昵称模糊搜索）
- 好友申请（支持验证消息）
- 申请处理（同意 / 拒绝，状态追踪）
- 好友备注（设置别名）
- 删除好友（双向解除关系）
- 好友列表（在线/离线分类、昵称/备注显示）

### 👪 群组管理

- 创建群聊（从好友列表多选成员）
- 加入已有群组
- 查看群成员（含在线状态）
- 邀请好友入群
- 群设置：修改群名称（群主/管理员）
- 成员管理：设置/取消管理员、踢出成员
- 群内系统消息（名称变更通知等）

### 📁 文件传输

- 服务器中继模式：发送方上传 → 服务器缓冲 → 接收方下载
- 支持拖拽文件到传输面板
- 多文件同时上传
- 上传文件删除
- 传输状态追踪（进行中 / 成功 / 失败）
- Base64 编码分块传输

### 🤖 AI 智能问答

- 集成 **DeepSeek API**（`deepseek-v4-flash` 模型）
- **流式输出**：SSE 逐词返回，实时显示
- **Markdown 渲染**：标题、列表、引用、代码块（语法高亮）、链接
- **多轮对话**：同一会话内保持上下文
- **会话管理**：创建/切换/删除对话历史
- **文件附件**：支持上传 txt/md/py/pdf 等代码/文本文件供 AI 分析
- 系统提示词定制为校园教学辅助角色

### 🔒 安全保障

- **传输加密**：AES-CBC 模式，随机 IV，每消息独立加密
- **密码哈希**：SHA256 + 随机盐值存储
- **防重放**：会话绑定用户 ID，防止身份伪造

---

## 快速开始

### 环境要求

- Python 3.10+
- MySQL 8.0+
- Conda（推荐）或 venv

### 1. 创建虚拟环境

```bash
conda create -n cdesign python=3.10 -y
conda activate cdesign
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
mysql -u root -p < init.sql
```

该脚本会创建数据库 `campus_im`，建立 7 张数据表，并插入预置测试数据。

### 4. 配置服务器

编辑 `server_config.ini`，修改数据库密码和 AI API 密钥：

```ini
[database]
password = 你的MySQL密码

[ai]
api_key = 你的DeepSeek_API_Key
```

> ⚠️ **安全提醒**：配置文件中的密钥仅用于本地开发测试，请勿将真实密钥提交到版本控制。

### 5. 启动服务器

```bash
python -m server.app
```

看到 `服务器已启动，监听 0.0.0.0:9000` 即表示启动成功。

### 6. 启动客户端

```bash
python -m client.app
```

在登录窗口输入测试账号即可登录。可同时启动多个客户端实例，用不同账号测试通信功能。

---

## 配置说明

### 服务器配置 (`server_config.ini`)

| 配置节 | 键 | 说明 | 默认值 |
|--------|-----|------|--------|
| `[database]` | `host` | MySQL 主机地址 | `127.0.0.1` |
| | `port` | MySQL 端口 | `3306` |
| | `user` | 数据库用户名 | `root` |
| | `password` | 数据库密码 | 需自行填写 |
| | `database` | 数据库名称 | `campus_im` |
| `[server]` | `host` | 监听地址 | `0.0.0.0` |
| | `port` | 监听端口 | `9000` |
| `[security]` | `aes_key` | AES 加密密钥（32 字节） | `campus_im_demo_key_32bytes!!` |
| `[ai]` | `api_url` | DeepSeek API 地址 | `https://api.deepseek.com/v1/chat/completions` |
| | `api_key` | DeepSeek API 密钥 | 需自行填写 |
| | `model` | 使用的模型 | `deepseek-v4-flash` |
| | `ai_user_id` | AI 助手对应的用户 ID | `1` |

### 客户端配置 (`client_config.ini`)

| 配置节 | 键 | 说明 | 默认值 |
|--------|-----|------|--------|
| `[server]` | `host` | 服务器地址 | `127.0.0.1` |
| | `port` | 服务器端口 | `9000` |
| `[security]` | `aes_key` | AES 密钥（需与服务器一致） | `campus_im_demo_key_32bytes!!` |

---

## 通信协议

### 消息格式

```
┌──────────────────┬─────────────────────────────┐
│  4 bytes (大端)   │       UTF-8 JSON 正文        │
│  正文长度 (N)     │         N 字节               │
└──────────────────┴─────────────────────────────┘
```

每条消息由 **4 字节长度前缀**（big-endian unsigned int）和紧随其后的 **UTF-8 编码 JSON 正文** 组成。

### 消息类型

所有消息类型常量定义在 `common/messages.py` 的 `MT` 类中，涵盖以下类别：

| 类别 | 消息类型示例 | 数量 |
|------|-------------|:---:|
| 用户 | `LOGIN`, `REGISTER`, `LOGOUT` | 3 |
| 聊天 | `CHAT`, `ROOM_CHAT`, `HISTORY_REQ`, `HISTORY_DELETE` | 4 |
| 好友 | `FRIEND_SEARCH`, `FRIEND_ADD`, `FRIEND_AGREE`, `FRIEND_REJECT`, `FRIEND_REMOVE`, `FRIEND_REMARK`, `FRIEND_REQ_LIST` | 7 |
| 群组 | `GROUP_CREATE`, `GROUP_LIST`, `GROUP_MEMBERS`, `GROUP_INVITE`, `GROUP_SETTINGS`, `GROUP_JOIN`, `GROUP_LEAVE` | 7 |
| 文件 | `FILE_REQ`, `FILE_DATA`, `FILE_END`, `FILE_ACCEPT`, `FILE_REJECT`, `FILE_DELETE` | 6 |
| AI | `AI_ASK`, `AI_ANSWER`, `AI_HISTORY`, `AI_HISTORY_DELETE` | 4 |
| 系统 | `ONLINE`, `OFFLINE`, `ERROR`, `SUCCESS` | 4+ |

### 请求/响应模式

每个请求消息包含 `msg_id` 字段，服务器处理后在响应中带回，客户端据此匹配请求与响应。

---

## 加密方案

### AES 端到端加密流程

```
发送方客户端                              接收方客户端
    │                                          │
    ├─ 1. 明文消息                              │
    ├─ 2. 生成 16 字节随机 IV                    │
    ├─ 3. AES-CBC 加密 (32 字节密钥)            │
    ├─ 4. Base64(IV + 密文) ──→ 服务器 ──→      │
    │                    (解密存储明文)           │
    │                    (转发密文)      ├─ 5. Base64 解码
    │                                          ├─ 6. 提取 IV + 密文
    │                                          ├─ 7. AES-CBC 解密
    │                                          └─ 8. 明文消息
```

### 关键细节

- **加密算法**：AES-256-CBC（32 字节密钥）
- **IV 生成**：`Crypto.Random.get_random_bytes(16)`，每条消息独立
- **编码格式**：Base64(16 字节 IV + 密文)
- **密钥协商**：客户端与服务器共享预设密钥（通过配置文件）
- **容错处理**：解密失败时返回原始密文，兼容未加密数据

---

## 数据库设计

### ER 概要

```
user ──┬── friend (user_id / friend_id) ──── user
       │
       ├── message (sender_id / receiver_id)
       │
       ├── file_record (sender_id / receiver_id)
       │
       ├── friend_request (from_user_id / to_user_id)
       │
       └── group_member (user_id)
                │
                └── chat_group (group_id)
```

### 数据表一览

| 表名 | 说明 | 预置记录 | 关键字段 |
|------|------|:---:|------|
| `user` | 用户信息 | 10 | user_id, username, password_hash, salt, nickname, role |
| `message` | 聊天消息 | 10 | msg_id, sender_id, receiver_id, room_id, content, is_encrypted |
| `friend` | 好友关系 | 30 | user_id, friend_id, remark |
| `friend_request` | 好友申请 | 6 | from_user_id, to_user_id, status, message |
| `chat_group` | 群聊信息 | 3 | group_id, name, owner_id |
| `group_member` | 群成员 | 11 | group_id, user_id, role |
| `file_record` | 文件传输 | 5 | file_id, sender_id, receiver_id, filename, size, status |

### 预置测试账号

| 用户名 | 密码 | 昵称 | 角色 |
|--------|------|------|------|
| `test1` | `test1` | 测试用户1 | 学生 |
| `dongjh` | `dongjh` | 董钧豪 | 学生 |
| `guoxt` | `guoxt` | 郭玄同 | 学生 |
| `zhujj` | `zhujj` | 朱俊基 | 学生 |
| `wujh` | `wujh` | 武家辉 | 学生 |
| `zhaozj` | `zhaozj` | 赵紫娟老师 | 教师 |
| `liming` | `liming` | 李明 | 学生 |
| `wangf` | `wangf` | 王芳 | 学生 |
| `chenx` | `chenx` | 陈曦 | 学生 |
| `ai` | `ai` | AI助手 | AI |

> 密码均与用户名相同，方便测试。

### 预置群组

| 群名 | 群主 | 说明 |
|------|------|------|
| 公共聊天室 | system | 全服可见，ID=1 |
| 课程设计讨论组 | zhujj | 课程设计专用 |
| 软件2406班 | dongjh | 班级群 |

---

## 项目结构

```
campus_im/
│
├── common/                     # 🔗 公共契约层（Client/Server 共享）
│   ├── messages.py             #   消息类型常量定义（MT 类, ~50 种）
│   ├── protocol.py             #   长度前缀编解码（send_msg / recv_msg）
│   └── crypto.py               #   AES-CBC 加密/解密工具
│
├── server/                     # 🖥️ 服务器端
│   ├── app.py                  #   装配入口（ChatServer 启动）
│   ├── config.py               #   配置文件读取
│   ├── core/                   #   服务器框架
│   │   ├── server.py           #     TCP accept 循环
│   │   ├── client_handler.py   #     每连接线程（收/发/分发/清理）
│   │   ├── session.py          #     会话对象（绑定 user_id）
│   │   ├── router.py           #     消息类型 → 处理函数注册表
│   │   ├── context.py          #     DI 容器（DAOs + 在线注册表 + 线程池）
│   │   └── online.py           #     线程安全在线用户注册表
│   ├── db/                     #   数据访问层
│   │   ├── pool.py             #     DBUtils 连接池封装
│   │   ├── base_dao.py         #     DAO 基类（_query / _query_one / _execute）
│   │   └── daos.py             #     7 个 DAO 实现
│   └── modules/                #   业务模块（注册到 MessageRouter）
│       ├── user.py             #     用户：登录/注册/注销
│       ├── chat.py             #     聊天：私聊/群聊/历史记录
│       ├── friend.py           #     好友：搜索/添加/同意/拒绝/删除/备注
│       ├── group.py            #     群组：创建/加入/邀请/设置/踢出
│       ├── file.py             #     文件：中继传输/多文件
│       └── ai.py               #     AI：DeepSeek 流式问答/会话管理
│
├── client/                     # 🖥️ 客户端
│   ├── app.py                  #   装配入口（ChatClient + 面板注册）
│   ├── config.py               #   配置文件读取
│   ├── state.py                #   全局状态管理（用户/好友/在线状态）
│   ├── core/                   #   客户端框架
│   │   ├── network.py          #     NetworkClient（TCP + 信号分发）
│   │   ├── main_window.py      #     MainWindow（导航栏 + 面板栈）
│   │   └── base_panel.py       #     BasePanel 基类（app/net/state 引用）
│   └── ui/                     #   UI 面板
│       ├── login_window.py     #     登录/注册窗口
│       ├── chat_panel.py       #     聊天面板（~1200 行，核心界面）
│       ├── friend_panel.py     #     好友管理面板
│       ├── file_panel.py       #     文件传输面板
│       └── ai_panel.py         #     AI 问答面板（Markdown 渲染）
│
├── test/                       # 🧪 测试
│   ├── unit/                   #   单元测试（按开发者组织）
│   │   ├── dhn/                #     AI 模块测试
│   │   ├── djh/                #     聊天/加密/好友/群组测试
│   │   ├── gxt/                #     文件面板/文件服务测试
│   │   ├── wjh/                #     用户模块测试
│   │   └── zjj/                #     在线状态/协议测试
│   ├── integration/            #   集成测试
│   └── system/                 #   系统级测试
│
├── icon/                       # 🎨 应用资源
│   └── logo.png                #   应用图标
│
├── init.sql                    # 建库脚本（DDL + 预置数据）
├── server_config.ini           # 服务器配置文件
├── client_config.ini           # 客户端配置文件
├── requirements.txt            # Python 依赖清单
├── pytest.ini                  # Pytest 配置
└── README.md                   # 项目文档
```

---

## 测试

项目包含完整的三层测试体系，覆盖从单元到端到端的全链路验证：

```bash
# 运行所有测试
pytest

# 按层级筛选
pytest -m unit           # 单元测试
pytest -m integration    # 集成测试
pytest -m "not slow"     # 排除慢速测试

# 生成覆盖率报告
pytest --cov=. --cov-report=html
```

### 单元测试 (`test/unit/`)

按开发者组织，验证各模块独立功能：

| 文件 | 覆盖模块 |
|------|---------|
| `wjh/test_user.py` | 用户认证、密码哈希 |
| `djh/test_chat.py` | 私聊/群聊消息处理 |
| `djh/test_crypto.py` | AES 加解密 |
| `djh/test_friend.py` | 好友搜索/添加/删除 |
| `djh/test_group.py` | 群组创建/成员管理 |
| `dhn/test_ai_module.py` | DeepSeek API 调用、流式解析 |
| `gxt/test_file_panel.py` | 文件传输面板逻辑 |
| `gxt/test_file_server.py` | 服务器文件中继 |
| `zjj/test_online_status.py` | 在线状态管理 |

### 集成测试 (`test/integration/`)

验证模块间协作与边界交互：

| 文件 | 覆盖场景 |
|------|---------|
| `test_user_flow_integration.py` | 注册 → 登录 → 注销完整流程 |
| `test_chat_flow_integration.py` | 私聊/群聊消息加密传输全链路 |
| `test_friend_flow_integration.py` | 好友申请 → 同意 → 删除完整流程 |
| `test_group_flow_integration.py` | 创建群组 → 邀请成员 → 退出 |
| `test_protocol_crypto_integration.py` | 协议编解码 + 加解密联合验证 |
| `test_server_integration.py` | 服务器启动、连接管理、路由分发 |

### 系统测试 (`test/system/`)

端到端验证，模拟真实用户场景：

| 文件 | 覆盖场景 |
|------|---------|
| `test_login_system.py` | 多用户登录/注销/异常登录处理 |
| `test_chat_system.py` | 多客户端实时通信、离线消息 |
| `test_multi_client.py` | 多客户端并发连接与状态同步 |
| `test_server_lifecycle.py` | 服务器启动/停止/异常恢复 |
| `test_user_journey.py` | 完整用户旅程（注册→加好友→建群→聊天→传文件→AI问答） |

---

## 开发团队

| 成员 | 负责模块 | 核心工作 |
|------|---------|---------|
| **朱俊基** | 服务器框架 / 数据访问层 / 消息协议 | TCP 服务框架、DAO 层设计、在线状态管理、协议定义、UI界面美化 |
| **郭玄同** | 客户端框架 / 文件传输模块 | PyQt5 客户端框架、NetworkClient、文件中继传输 |
| **武家辉** | 用户管理 / 登录注册 | 用户认证、密码哈希、注册登录 UI |
| **董钧豪** | 聊天面板 / 好友面板 / 加密实现 | 私聊/群聊 UI、好友管理、AES 加密方案 |
| **董浩楠** | AI 问答模块 | DeepSeek API 集成、SSE 流式处理、Markdown 渲染 |

---

## 许可证

本项目仅用于课程设计学习目的，不适用于生产环境。
