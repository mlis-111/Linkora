-- Active: 1781965733262@@127.0.0.1@3306@campus_im
-- 校园即时通信系统数据库初始化脚本

-- 创建数据库
DROP DATABASE IF EXISTS campus_im;
CREATE DATABASE campus_im DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE campus_im;
SET NAMES utf8mb4;
-- 创建用户表
CREATE TABLE user (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(64) NOT NULL,
    salt VARCHAR(32) NOT NULL,
    nickname VARCHAR(50),
    is_ai_bot TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建消息表
CREATE TABLE message (
    message_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    msg_type TINYINT NOT NULL COMMENT '1=私聊, 2=群聊',
    sender_id INT NOT NULL,
    receiver_id INT COMMENT '私聊时有值',
    room_id INT COMMENT '群聊时有值',
    content TEXT NOT NULL COMMENT '存储明文',
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_p2p (sender_id, receiver_id, sent_at),
    INDEX idx_room (room_id, sent_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建好友表
CREATE TABLE friend (
    user_id INT NOT NULL,
    friend_id INT NOT NULL,
    remark VARCHAR(50),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, friend_id),
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建文件传输记录表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建好友申请表
CREATE TABLE friend_request (
    id INT PRIMARY KEY AUTO_INCREMENT,
    from_id INT NOT NULL,
    to_id INT NOT NULL,
    message VARCHAR(200) DEFAULT '' COMMENT '申请附言',
    status TINYINT DEFAULT 0 COMMENT '0=待处理 1=已同意 2=已拒绝',
    reject_reason VARCHAR(200) DEFAULT '' COMMENT '拒绝理由',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_to (to_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建群聊表
CREATE TABLE chat_group (
    group_id INT PRIMARY KEY AUTO_INCREMENT,
    group_name VARCHAR(100) NOT NULL,
    owner_id INT COMMENT '群主，公共群为 NULL',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建群成员表
CREATE TABLE group_member (
    group_id INT NOT NULL,
    user_id INT NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    role   TINYINT     NOT NULL DEFAULT 0 COMMENT '0=成员, 1=管理员',
    remark VARCHAR(100) NOT NULL DEFAULT '' COMMENT '用户对该群的个人备注',
    PRIMARY KEY (group_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 插入默认公共群聊（固定 ID=1，与 PUBLIC_ROOM_ID=1 对应）
INSERT INTO chat_group (group_id, group_name, owner_id) VALUES (1, '公共聊天室', NULL);

-- 插入预置数据
-- AI账号 (user_id=1, password: ai123456)
INSERT INTO user (username, password_hash, salt, nickname, is_ai_bot) VALUES
('ai_assistant', 'e10adc3949ba59abbe56e057f20f883e', '00000000000000000000000000000000', 'AI助手', 1);

-- 测试账号 (所有密码都与用户名相同)
-- test1/test1
INSERT INTO user (username, password_hash, salt, nickname, is_ai_bot) VALUES
('test1', 'cc03e747a6afbbcbf8be7668acfebee5', '11111111111111111111111111111111', '测试用户1', 0);

-- test2/test2
INSERT INTO user (username, password_hash, salt, nickname, is_ai_bot) VALUES
('test2', 'ad0234829205b9033196ba818f7a872b', '22222222222222222222222222222222', '测试用户2', 0);

-- test3/test3
INSERT INTO user (username, password_hash, salt, nickname, is_ai_bot) VALUES
('test3', '8ad8757baa8564dc136c1e07507f4a98', '33333333333333333333333333333333', '测试用户3', 0);

-- 显示创建结果
SELECT '数据库初始化完成!' AS status;
SELECT * FROM user;
