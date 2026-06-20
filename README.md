# 校园即时通信与文件传输系统

## 项目简介

基于Python的校园即时通信系统，支持用户注册登录、私聊、群聊、好友管理、文件传输和AI问答功能。

## 技术栈

- **后端**: Python 3.10 / socket / 多线程
- **数据库**: MySQL 8.0+ / pymysql / DBUtils
- **前端**: CustomTkinter
- **加密**: pycryptodome (AES对称加密)
- **协议**: 长度前缀(4字节) + JSON

## 快速开始

### 1. 安装依赖

```bash
conda create -n cdesign python=3.10 --y
conda activate cdesign
pip install -r requirements.txt
```

### 2. 初始化数据库

```bash
mysql -u root -p < init.sql
```

### 3. 配置服务器和客户端（改完后记得将文件后缀的.example去掉）

**服务器配置（server_config.ini）：**
```ini
[database]
password = 你的MySQL密码

# 其他配置项保持默认即可
```

**客户端配置（client_config.ini）：**
```ini
[server]
host = 127.0.0.1
port = 9000

# 其他配置项保持默认即可
```

**注意：** 配置文件已自动生成，只需修改 `server_config.ini` 中的数据库密码即可。

### 4. 启动服务器

```bash
python -m server.app
```

### 5. 启动客户端

```bash
python -m client.app
```

## 测试账号

系统预置了以下测试账号：

- test1 / test1
- test2 / test2
- test3 / test3
- ai_assistant / ai123456 (AI账号)

## 项目结构

```
campus_im/
├── common/          # 公共契约层
├── server/          # 服务器端
│   ├── core/       # 服务器框架
│   ├── db/         # 数据访问层
│   └── modules/    # 业务模块
├── client/          # 客户端
│   ├── core/       # 客户端框架
│   └── ui/         # UI面板
└── test/            # 测试代码
```

## 功能特性

- ✅ 用户注册与登录
- ✅ 在线用户列表
- ✅ 一对一私聊
- ✅ 公共聊天室
- ✅ 好友管理与备注
- ✅ 文件传输
- ✅ 消息加密（AES）
- ✅ AI问答

## 开发团队

- 朱俊基：框架搭建、数据访问层
- 郭玄同：客户端框架、文件传输
- 武家辉：用户管理
- 董钧豪：聊天、好友、加密
- 董浩楠：AI问答

## 许可证

本项目仅用于课程设计学习目的。
