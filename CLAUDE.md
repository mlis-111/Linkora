# 校园即时通信与文件传输系统 · AI 工作指令
## 先前介绍
环境用的是conda，名字叫cdesign,UI库换成PyQt5了,ui界面的设计跟本地C:\Users\21857\Desktop\ui.zip里面的风格一样，先不用push,我让你push的时候再说


## 项目概述

基于 Python 的校园即时通信系统（Campus IM），支持用户注册登录、私聊、群聊、好友管理、文件传输和 AI 问答功能。

## 核心成员信息

- **董钧豪** 的 Claude AI 助手
- 董钧豪负责模块：聊天模块（chat）、好友模块（friend）、加密模块（CryptoUtil）
- 协作成员：朱俊基（框架/DAO）、郭玄同（客户端框架/文件）、武家辉（用户管理）、董浩楠（AI问答）

## 编码规范

1. 每个 `.py` 文件的文档注释中 `author` 写 `董钧豪`
2. 在 `feature-djh` 分支上编码，不直接 push 到 dev/main
3. 每完成一个功能 commit 一次，允许多次 commit
4. 编码完成后写单元测试（6种覆盖），放在 `test/unit/djh/`
5. 创建 PR 到 dev 分支，PR 描述写明完成了哪些功能及描述
6. PR 后在告诉我，我自己会提醒审核，审核跑测试、查命名规范、查契约遵守、验功能正确
7. 审核通过自动合并，有冲突手动解决
8. 严格遵守契约字段名，不自创字段；按定好的接口编码
9. 6月24日中午前至少一次 PR 被通过

## 技术约定

- **消息协议**：4字节长度前缀（网络字节序）+ JSON 消息体
- **加密方式**：AES 对称加密（pycryptodome），随机 IV，Base64(IV+密文)
- **数据库**：MySQL 8.0+，通过 DAO（ctx.db.*）访问，不直接写 SQL
- **消息类型**：定义在 `common/messages.py` 的 `MT` 类中
- **服务器路由**：`MessageRouter.register()` 注册式分发，业务模块零 import
- **客户端通信**：`NetworkClient.on()` 订阅消息，回调在 GUI 线程执行

## 文件归属

| 文件 | 负责人 |
|------|--------|
| `common/crypto.py` | 董钧豪 |
| `server/modules/chat.py` | 董钧豪 |
| `server/modules/friend.py` | 董钧豪 |
| `client/ui/chat_panel.py` | 董钧豪 |
| `client/ui/friend_panel.py` | 董钧豪 |
| `test/unit/djh/` | 董钧豪 |
