-- 校园即时通信系统数据库初始化脚本

DROP DATABASE IF EXISTS campus_im;
CREATE DATABASE campus_im DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE campus_im;
SET NAMES utf8mb4;

-- ============================================================
-- DDL
-- ============================================================

CREATE TABLE user (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(64) NOT NULL,
    salt VARCHAR(32) NOT NULL,
    nickname VARCHAR(50),
    is_ai_bot TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE message (
    message_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    msg_type TINYINT NOT NULL COMMENT '1=私聊, 2=群聊',
    sender_id INT NOT NULL,
    receiver_id INT COMMENT '私聊时有值',
    room_id INT COMMENT '群聊时有值',
    content TEXT NOT NULL COMMENT '存储明文',
    conv_id BIGINT DEFAULT NULL COMMENT 'AI对话ID（非AI消息为NULL）',
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_p2p (sender_id, receiver_id, sent_at),
    INDEX idx_room (room_id, sent_at),
    INDEX idx_conv (conv_id, sent_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE friend (
    user_id INT NOT NULL,
    friend_id INT NOT NULL,
    remark VARCHAR(50),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, friend_id),
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE file_record (
    file_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    sender_id INT NOT NULL,
    receiver_id INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    status TINYINT DEFAULT 0 COMMENT '0=传输中, 1=成功, 2=失败',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    transferred_at TIMESTAMP NULL,
    INDEX idx_sender (sender_id, created_at),
    INDEX idx_receiver (receiver_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE friend_request (
    id INT PRIMARY KEY AUTO_INCREMENT,
    from_id INT NOT NULL,
    to_id INT NOT NULL,
    message VARCHAR(200) DEFAULT '',
    status TINYINT DEFAULT 0 COMMENT '0=待处理 1=已同意 2=已拒绝',
    reject_reason VARCHAR(200) DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_to (to_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE chat_group (
    group_id INT PRIMARY KEY AUTO_INCREMENT,
    group_name VARCHAR(100) NOT NULL,
    owner_id INT COMMENT '群主，公共群为 NULL',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE group_member (
    group_id INT NOT NULL,
    user_id INT NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    role   TINYINT     NOT NULL DEFAULT 0 COMMENT '0=成员, 1=管理员',
    remark VARCHAR(100) NOT NULL DEFAULT '',
    PRIMARY KEY (group_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 用户数据（10 条，密码均为 username）
-- ============================================================

-- MD5: SELECT MD5('username')
INSERT INTO user (username, password_hash, salt, nickname, is_ai_bot) VALUES
('ai',        MD5('ai'),        'ai_salt_32_bytes_xxxxxxxxxxxxxx', 'AI助手',      1),
('test1',     MD5('test1'),     't1_salt_32_bytes_xxxxxxxxxxxxxx', '测试用户1',   0),
('dongjh',    MD5('dongjh'),    'dj_salt_32_bytes_xxxxxxxxxxxxxx', '董钧豪',      0),
('guoxt',     MD5('guoxt'),     'gx_salt_32_bytes_xxxxxxxxxxxxxx', '郭玄同',      0),
('zhujj',     MD5('zhujj'),     'zj_salt_32_bytes_xxxxxxxxxxxxxx', '朱俊基',      0),
('wujh',      MD5('wujh'),      'wj_salt_32_bytes_xxxxxxxxxxxxxx', '武家辉',      0),
('zhaozj',    MD5('zhaozj'),    'zz_salt_32_bytes_xxxxxxxxxxxxxx', '赵紫娟老师',  0),
('liming',    MD5('liming'),    'lm_salt_32_bytes_xxxxxxxxxxxxxx', '李明',        0),
('wangf',     MD5('wangf'),     'wf_salt_32_bytes_xxxxxxxxxxxxxx', '王芳',        0),
('chenx',     MD5('chenx'),     'cx_salt_32_bytes_xxxxxxxxxxxxxx', '陈曦',        0);

-- ============================================================
-- 群聊（3 个）   公共聊天室(固定ID=1) + 2个用户群
-- ============================================================
INSERT INTO chat_group (group_id, group_name, owner_id) VALUES
(1, '公共聊天室', NULL),
(2, '课程设计讨论组', 3),
(3, '软件2406班群', 5);

-- 群成员
INSERT INTO group_member (group_id, user_id, role) VALUES
-- 课程设计讨论组
(2, 3, 1), (2, 4, 0), (2, 5, 0), (2, 6, 0),
-- 软件2406班群
(3, 5, 1), (3, 3, 0), (3, 4, 0), (3, 7, 0), (3, 8, 0), (3, 9, 0), (3, 10, 0);

-- ============================================================
-- 好友关系（test1 为中心，每人 3-7 个好友）
-- ============================================================
INSERT INTO friend (user_id, friend_id, remark) VALUES
-- test1 的好友
(2, 3, '钧豪'),   (3, 2, ''),
(2, 4, '玄同'),   (4, 2, ''),
(2, 5, '俊基'),   (5, 2, ''),
(2, 6, '家辉'),   (6, 2, ''),
(2, 7, '紫娟老师'), (7, 2, ''),
(2, 8, '小明'),   (8, 2, ''),
(2, 9, '小芳'),   (9, 2, ''),
-- 项目成员互加
(3, 4, '玄同'),   (4, 3, '钧豪'),
(3, 5, '俊基'),   (5, 3, '钧豪'),
(3, 6, '家辉'),   (6, 3, '钧豪'),
(4, 5, '俊基'),   (5, 4, '玄同'),
(4, 6, '家辉'),   (6, 4, '玄同'),
(5, 6, '家辉'),   (6, 5, '俊基'),
-- 同学互加
(8, 9, '芳芳'),   (9, 8, '明哥'),
(8, 10, '曦曦'),  (10, 8, ''),
(9, 10, ''),      (10, 9, '');

-- ============================================================
-- 好友申请（6 条，含待处理/已同意/已拒绝）
-- ============================================================
INSERT INTO friend_request (from_id, to_id, message, status, reject_reason) VALUES
(7, 2, '我是赵老师，加一下', 0, ''),                          -- 待处理
(10, 2, '你好，加个好友吧', 0, ''),                            -- 待处理
(4, 8, '课程设计一起组队？', 1, ''),                           -- 已同意
(9, 2, '', 2, '暂时不加'),                                    -- 已拒绝（收到了拒绝）
(2, 10, '我是 test1', 0, ''),                                 -- test1 发出的（等待）
(2, 7, '赵老师您好', 1, '');                                  -- test1 发出的（已同意）

-- ============================================================
-- 聊天消息（私聊 + 群聊，约 8 条）
-- ============================================================
INSERT INTO message (msg_type, sender_id, receiver_id, room_id, content) VALUES
-- 私聊
(1, 3, 2, NULL, 'test1 在吗？AES加密方案我写好了'),
(1, 2, 3, NULL, '在的，发我看看'),
(1, 3, 2, NULL, '好的，我发你邮箱了'),
(1, 4, 2, NULL, '客户端框架我提交了，你拉一下'),
(1, 2, 4, NULL, '收到 👍'),
-- 公共聊天室
(2, 5, NULL, 1, '@所有人 今晚8点线上对进度，收到回复'),
(2, 3, NULL, 1, '收到'),
(2, 6, NULL, 1, '没问题'),
-- 课程设计讨论组
(2, 4, NULL, 2, '大家把各自的模块进度报一下'),
(2, 3, NULL, 2, '我的加密模块已完成，可以联调了');

-- ============================================================
-- 文件传输记录（5 条）
-- ============================================================
INSERT INTO file_record (sender_id, receiver_id, file_name, file_size, status) VALUES
(3, 2, 'AES加密方案.pdf', 2516582, 1),
(4, 2, '客户端框架v2.zip', 10485760, 1),
(5, 3, '数据库设计文档.docx', 524288, 1),
(2, 3, '需求变更说明.txt', 2048, 1),
(6, 4, '登录模块测试报告.pdf', 3145728, 0);

-- ============================================================
SELECT '数据库初始化完成!' AS status;
SELECT * FROM user;
