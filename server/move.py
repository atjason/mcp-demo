"""
机器人运动能力 MCP 服务：纯模拟，通过打印模拟执行，不连接真实硬件。
"""
import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "move-mcp",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8004")),
)

# 模拟状态（供 robot_get_status 使用）
_state = {
    "posture": "unknown",  # stand | lie_down | unknown
    "gait_mode": "walk",    # walk | run
    "emergency_stop": False,
}


@mcp.tool()
def robot_stand() -> str:
    """
    让机器人站立。无参数。
    """
    print("模拟：机器人站立")
    _state["posture"] = "stand"
    return "已执行：机器人已站立。"


@mcp.tool()
def robot_lie_down() -> str:
    """
    让机器人趴下。无参数。
    """
    print("模拟：机器人趴下")
    _state["posture"] = "lie_down"
    return "已执行：机器人已趴下。"


@mcp.tool()
def robot_walk(direction: str, steps: int) -> str:
    """
    机器人行走。direction 为 "forward"（前）或 "backward"（后），steps 为步数（正整数）。
    """
    dir_cn = "前" if direction == "forward" else "后"
    print(f"模拟：向{dir_cn}走 {steps} 步")
    return f"已执行：向{dir_cn}走 {steps} 步。"


@mcp.tool()
def robot_turn(direction: str, degrees: float) -> str:
    """
    机器人转向。direction 为 "left"（左）或 "right"（右），degrees 为角度（如 30）。
    """
    dir_cn = "左" if direction == "left" else "右"
    print(f"模拟：{dir_cn}转 {degrees} 度")
    return f"已执行：{dir_cn}转 {degrees} 度。"


@mcp.tool()
def robot_set_gait_mode(mode: str) -> str:
    """
    切换步态模式。mode 为 "walk"（行走）或 "run"（跑步）。
    """
    mode_cn = "行走" if mode == "walk" else "跑步"
    print(f"模拟：切换为{mode_cn}模式")
    _state["gait_mode"] = mode
    return f"已执行：已切换为{mode_cn}模式。"


@mcp.tool()
def robot_emergency_stop(enable: bool) -> str:
    """
    开启或关闭软件急停。enable 为 True 表示开启急停，False 表示关闭。
    """
    if enable:
        print("模拟：开启软件急停")
        _state["emergency_stop"] = True
        return "已执行：已开启软件急停。"
    else:
        print("模拟：关闭软件急停")
        _state["emergency_stop"] = False
        return "已执行：已关闭软件急停。"


@mcp.tool()
def robot_get_status() -> str:
    """
    获取当前机器人模拟状态摘要：姿态、步态模式、急停是否开启。
    """
    posture_cn = {"stand": "站立", "lie_down": "趴下"}.get(_state["posture"], _state["posture"])
    gait_cn = {"walk": "行走", "run": "跑步"}.get(_state["gait_mode"], _state["gait_mode"])
    stop_cn = "开启" if _state["emergency_stop"] else "关闭"
    msg = f"姿态={posture_cn}，步态模式={gait_cn}，软件急停={stop_cn}"
    print(f"模拟：查询状态 -> {msg}")
    return f"当前状态：{msg}。"


if __name__ == "__main__":
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))
