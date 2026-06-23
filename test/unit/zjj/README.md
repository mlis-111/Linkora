# 朱俊基的单元测试

负责人：朱俊基  
功能模块：在线状态实时显示  
测试框架：pytest

## 测试文件

### test_online_status.py
测试在线状态管理和用户列表更新功能

#### 测试类

1. **TestOnlineRegistry** - 测试服务器端在线用户管理 (8个测试)
   - `test_add_user` - 测试添加在线用户
   - `test_remove_user` - 测试移除在线用户
   - `test_online_ids` - 测试获取所有在线用户ID列表
   - `test_duplicate_login` - 测试重复登录检测
   - `test_send_to_online_user` - 测试向在线用户发送消息
   - `test_send_to_offline_user` - 测试向离线用户发送消息
   - `test_broadcast` - 测试广播消息（排除指定用户）
   - `test_broadcast_to_all` - 测试广播消息给所有人

2. **TestClientState** - 测试客户端状态管理 (4个测试)
   - `test_initial_state` - 测试初始状态
   - `test_set_user_info` - 测试设置用户信息
   - `test_update_online_users` - 测试更新在线用户列表
   - `test_update_all_users` - 测试更新所有用户列表

3. **TestOnlineStatusLogic** - 测试在线状态判断逻辑 (5个测试)
   - `test_check_user_online` - 测试检查用户是否在线
   - `test_count_online_users` - 测试统计在线人数
   - `test_user_status_text` - 测试用户状态文本生成
   - `test_empty_online_list` - 测试空的在线用户列表
   - `test_all_users_online` - 测试所有用户都在线的情况

4. **TestUserListUpdate** - 测试用户列表更新逻辑 (4个测试)
   - `test_parse_user_list_message` - 测试解析USER_LIST消息
   - `test_parse_login_response` - 测试解析登录响应消息
   - `test_parse_login_failure` - 测试解析登录失败响应
   - `test_missing_fields` - 测试缺少字段的消息

5. **TestParameterized** - 参数化测试 (2个测试)
   - `test_user_online_status` - 参数化测试用户在线状态（4个参数组合）
   - `test_online_count_text` - 参数化测试在线人数文本（4个参数组合）

6. **特殊测试**
   - `test_large_user_list` - 测试大量用户场景（标记为@slow）
   - `test_zero_users` - 测试零用户边界情况（标记为@edge_case）

## 运行测试

### 基本命令

```bash
# 切换到项目根目录
cd d:/A-E-drive/Course-Design/campus_im

# 运行所有测试
pytest test/unit/zjj/test_online_status.py

# 详细输出模式
pytest test/unit/zjj/test_online_status.py -v

# 显示打印输出
pytest test/unit/zjj/test_online_status.py -s

# 详细输出 + 打印输出
pytest test/unit/zjj/test_online_status.py -v -s
```

### 运行特定测试

```bash
# 运行单个测试类
pytest test/unit/zjj/test_online_status.py::TestOnlineRegistry -v

# 运行单个测试方法
pytest test/unit/zjj/test_online_status.py::TestOnlineRegistry::test_add_user -v

# 运行多个测试类
pytest test/unit/zjj/test_online_status.py::TestOnlineRegistry test/unit/zjj/test_online_status.py::TestClientState -v
```

### 使用标记过滤

```bash
# 排除慢速测试
pytest test/unit/zjj/test_online_status.py -v -m "not slow"

# 只运行边界情况测试
pytest test/unit/zjj/test_online_status.py -v -m "edge_case"

# 运行慢速测试
pytest test/unit/zjj/test_online_status.py -v -m "slow"
```

### 测试覆盖率

```bash
# 生成测试覆盖率报告
pytest test/unit/zjj/test_online_status.py --cov=server.core.online --cov=client.state --cov-report=html

# 查看覆盖率报告
# 打开 htmlcov/index.html

# 终端显示覆盖率
pytest test/unit/zjj/test_online_status.py --cov=server.core.online --cov=client.state --cov-report=term
```

### 失败时调试

```bash
# 失败时进入pdb调试器
pytest test/unit/zjj/test_online_status.py --pdb

# 只运行上次失败的测试
pytest test/unit/zjj/test_online_status.py --lf

# 先运行失败的，再运行其他的
pytest test/unit/zjj/test_online_status.py --ff
```

### 其他有用选项

```bash
# 显示最慢的10个测试
pytest test/unit/zjj/test_online_status.py --durations=10

# 并行运行测试（需要安装pytest-xdist）
pytest test/unit/zjj/test_online_status.py -n auto

# 生成JUnit XML报告
pytest test/unit/zjj/test_online_status.py --junitxml=test-results.xml

# 颜色输出
pytest test/unit/zjj/test_online_status.py --color=yes
```

## 测试覆盖范围

### 服务器端
- ✅ 在线用户注册表 (OnlineRegistry)
  - 添加/移除用户
  - 检查在线状态
  - 获取在线用户列表
  - 消息发送和广播
  - 重复登录处理

### 客户端
- ✅ 状态管理 (ClientState)
  - 用户信息存储
  - 在线用户列表更新
  - 所有用户列表更新

### 业务逻辑
- ✅ 在线状态判断
- ✅ 用户列表更新
- ✅ 消息解析
- ✅ 边界情况处理

### Fixtures（测试装置）
- `registry` - OnlineRegistry实例
- `client_state` - ClientState实例
- `mock_handler` - MockHandler实例
- `sample_all_users` - 示例所有用户数据
- `sample_online_users` - 示例在线用户数据

## 预期结果

所有测试应该通过，输出类似：
```
test/unit/zjj/test_online_status.py::TestOnlineRegistry::test_add_user PASSED
test/unit/zjj/test_online_status.py::TestOnlineRegistry::test_remove_user PASSED
test/unit/zjj/test_online_status.py::TestOnlineRegistry::test_online_ids PASSED
test/unit/zjj/test_online_status.py::TestOnlineRegistry::test_duplicate_login PASSED
test/unit/zjj/test_online_status.py::TestOnlineRegistry::test_send_to_online_user PASSED
test/unit/zjj/test_online_status.py::TestOnlineRegistry::test_send_to_offline_user PASSED
test/unit/zjj/test_online_status.py::TestOnlineRegistry::test_broadcast PASSED
test/unit/zjj/test_online_status.py::TestOnlineRegistry::test_broadcast_to_all PASSED
test/unit/zjj/test_online_status.py::TestClientState::test_initial_state PASSED
test/unit/zjj/test_online_status.py::TestClientState::test_set_user_info PASSED
test/unit/zjj/test_online_status.py::TestClientState::test_update_online_users PASSED
test/unit/zjj/test_online_status.py::TestClientState::test_update_all_users PASSED
test/unit/zjj/test_online_status.py::TestOnlineStatusLogic::test_check_user_online PASSED
test/unit/zjj/test_online_status.py::TestOnlineStatusLogic::test_count_online_users PASSED
test/unit/zjj/test_online_status.py::TestOnlineStatusLogic::test_user_status_text PASSED
test/unit/zjj/test_online_status.py::TestOnlineStatusLogic::test_empty_online_list PASSED
test/unit/zjj/test_online_status.py::TestOnlineStatusLogic::test_all_users_online PASSED
test/unit/zjj/test_online_status.py::TestUserListUpdate::test_parse_user_list_message PASSED
test/unit/zjj/test_online_status.py::TestUserListUpdate::test_parse_login_response PASSED
test/unit/zjj/test_online_status.py::TestUserListUpdate::test_parse_login_failure PASSED
test/unit/zjj/test_online_status.py::TestUserListUpdate::test_missing_fields PASSED
test/unit/zjj/test_online_status.py::TestParameterized::test_user_online_status[1-True] PASSED
test/unit/zjj/test_online_status.py::TestParameterized::test_user_online_status[2-False] PASSED
test/unit/zjj/test_online_status.py::TestParameterized::test_user_online_status[3-True] PASSED
test/unit/zjj/test_online_status.py::TestParameterized::test_user_online_status[4-False] PASSED
test/unit/zjj/test_online_status.py::TestParameterized::test_online_count_text[4-0-4 人 · 0 在线] PASSED
test/unit/zjj/test_online_status.py::TestParameterized::test_online_count_text[4-2-4 人 · 2 在线] PASSED
test/unit/zjj/test_online_status.py::TestParameterized::test_online_count_text[4-4-4 人 · 4 在线] PASSED
test/unit/zjj/test_online_status.py::TestParameterized::test_online_count_text[10-5-10 人 · 5 在线] PASSED

============================== 29 passed in 0.XXs ==============================
```

## pytest配置

可以在项目根目录创建 `pytest.ini` 配置文件：

```ini
[pytest]
testpaths = test
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    edge_case: marks tests as edge case tests
```

## 注意事项

1. 测试使用Mock对象模拟ClientHandler，避免依赖真实的网络连接
2. 使用pytest的fixture机制提供测试数据和对象
3. 使用参数化测试覆盖多种场景
4. 测试覆盖了核心业务逻辑，但不包括UI测试
5. 使用标记（markers）区分不同类型的测试
6. 如果需要集成测试，请参考 `test/integration-testing/` 目录

## 依赖

```bash
pip install pytest pytest-cov
```

## pytest优势

- ✅ 更简洁的断言语法 (`assert` 而不是 `self.assertEqual`)
- ✅ Fixture机制提供灵活的测试数据管理
- ✅ 参数化测试减少重复代码
- ✅ 丰富的插件生态系统
- ✅ 更详细的失败信息
- ✅ 易于集成CI/CD
