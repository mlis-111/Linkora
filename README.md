# 校园即时通信与文件传输系统

## 项目简介

基于 Python + PyQt5 的校园即时通信系统，支持用户注册登录、私聊、群聊、好友管理、文件传输和 AI 问答功能。

## 技术栈

- **后端**: Python 3.10 / socket / 多线程
- **数据库**: MySQL 8.0+ / pymysql / DBUtils
- **前端**: PyQt5
- **加密**: pycryptodome (AES 对称加密)
- **协议**: 长度前缀 (4 字节) + JSON

## 快速开始

### 1. 安装依赖

```bash
conda create -n cdesign python=3.10 -y
conda activate cdesign
pip install -r requirements.txt
```

### 2. 初始化数据库

```bash
mysql -u root -p < init.sql
```

### 3. 配置

修改 `server_config.ini` 中的数据库密码：

```ini
[database]
password = 你的MySQL密码
```

### 4. 启动服务器

```bash
python -m server.app
```

### 5. 启动客户端

```bash
python -m client.app
```

## 测试账号

| 用户名 | 密码 | 昵称 | 角色 |
|--------|------|------|------|
| test1 | test1 | 测试用户1 | 学生 |
| dongjh | dongjh | 董钧豪 | 学生 |
| guoxt | guoxt | 郭玄同 | 学生 |
| zhujj | zhujj | 朱俊基 | 学生 |
| wujh | wujh | 武家辉 | 学生 |
| zhaozj | zhaozj | 赵紫娟老师 | 教师 |
| liming | liming | 李明 | 学生 |
| wangf | wangf | 王芳 | 学生 |
| chenx | chenx | 陈曦 | 学生 |
| ai | ai | AI助手 | AI |

密码均与用户名相同。

## 数据库表

| 表 | 说明 | 预置数据 |
|------|------|:---:|
| user | 用户 | 10 条 |
| chat_group | 群聊 | 3 个 |
| group_member | 群成员 | 11 条 |
| friend | 好友关系 | 30 条 |
| friend_request | 好友申请 | 6 条 |
| message | 聊天记录 | 10 条 |
| file_record | 文件传输记录 | 5 条 |

## 项目结构

```
campus_im/
├── common/              # 公共契约层
│   ├── messages.py      # 消息类型常量
│   ├── protocol.py      # 长度前缀编解码
│   └── crypto.py        # AES 加密工具
├── server/              # 服务器端
│   ├── app.py           # 装配入口
│   ├── config.py        # 配置读取
│   ├── core/            # 服务器框架
│   ├── db/              # 数据访问层 (DAO)
│   └── modules/         # 业务模块 (user/chat/friend/group/file/ai)
├── client/              # 客户端
│   ├── app.py           # 装配入口
│   ├── state.py         # 全局状态
│   ├── core/            # 客户端框架 (network/base_panel/main_window)
│   └── ui/              # UI 面板 (login/chat/friend/file/ai)
├── init.sql             # 建库建表 + 预置数据
├── server_config.ini    # 服务器配置
├── client_config.ini    # 客户端配置
└── requirements.txt
```

## 功能特性

- 用户注册与登录（SHA256 + MD5 兼容）
- 实时私聊 / 群聊 / 公共聊天室
- 好友管理（添加、备注、删除）
- 好友申请（发送、接受、拒绝，状态可查）
- 创建群聊（多选好友）
- 群聊设置（改名、查看成员、退出）
- 文件传输（支持拖拽）
- 消息 AES 端到端加密
- AI 智能问答（DeepSeek API）
- 离线消息、历史记录持久化
- 在线 / 离线状态实时显示

## 开发团队

| 成员 | 负责 |
|------|------|
| 朱俊基 | 服务器框架、数据访问层、消息协议 |
| 郭玄同 | 客户端框架、文件传输模块 |
| 武家辉 | 用户管理、登录注册 |
| 董钧豪 | 聊天面板、好友面板、加密实现 |
| 董浩楠 | AI 问答模块 |

## 许可证

本项目仅用于课程设计学习目的。
