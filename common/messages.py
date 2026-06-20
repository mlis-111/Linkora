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

    # 文件传输
    FILE_REQ = "file_req"
    FILE_RESP = "file_resp"
    FILE_DATA = "file_data"
    FILE_END = "file_end"

    # AI
    AI_ASK = "ai_ask"
    AI_ANSWER = "ai_answer"

    # 错误
    ERROR = "error"


PUBLIC_ROOM_ID = 1


def error(code, message):
    """构造错误消息"""
    return {"type": MT.ERROR, "code": code, "message": message}
