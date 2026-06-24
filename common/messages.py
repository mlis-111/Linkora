class MT:
    """消息类型常量"""
    # 用户管理
    REGISTER = "register"
    REGISTER_RESP = "register_resp"
    LOGIN = "login"
    LOGIN_RESP = "login_resp"
    LOGOUT = "logout"
    USER_LIST = "user_list"

    # 聊天
    CHAT = "chat"
    ROOM_CHAT = "room_chat"
    HISTORY_REQ = "history_req"
    HISTORY_RESP = "history_resp"

    # 好友
    FRIEND_ADD = "friend_add"
    FRIEND_ADD_RESP = "friend_add_resp"
    FRIEND_REMARK = "friend_remark"
    FRIEND_LIST = "friend_list"
    FRIEND_LIST_RESP = "friend_list_resp"
    FRIEND_REQ_NOTIFY = "friend_req_notify"
    FRIEND_AGREE = "friend_agree"
    FRIEND_AGREE_RESP = "friend_agree_resp"
    FRIEND_REJECT = "friend_reject"
    FRIEND_REJECTED = "friend_rejected"  # 通知申请方被拒绝
    FRIEND_REQ_LIST = "friend_req_list"
    FRIEND_REQ_LIST_RESP = "friend_req_list_resp"

    # 文件传输
    FILE_REQ = "file_req"
    FILE_RESP = "file_resp"
    FILE_DATA = "file_data"
    FILE_END = "file_end"

    # AI
    AI_ASK = "ai_ask"
    AI_ANSWER = "ai_answer"

    # 群聊管理
    GROUP_CREATE = "group_create"
    GROUP_CREATE_RESP = "group_create_resp"
    GROUP_JOIN = "group_join"
    GROUP_JOIN_RESP = "group_join_resp"
    GROUP_LIST = "group_list"
    GROUP_LIST_RESP = "group_list_resp"
    GROUP_MEMBERS = "group_members"
    GROUP_MEMBERS_RESP = "group_members_resp"
    GROUP_INVITE = "group_invite"

    # 错误
    ERROR = "error"


PUBLIC_ROOM_ID = "group_public"


def error(code, message):
    """构造错误消息"""
    return {"type": MT.ERROR, "code": code, "message": message}
