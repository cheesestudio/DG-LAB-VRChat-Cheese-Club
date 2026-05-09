# 芝士郊狼控制软件

VRChat + DG-LAB 设备联动控制工具，属于**芝士郊狼台球后援会**（QQ群: 757992539）。

## 功能一览

| 功能 | 说明 |
|------|------|
| DG-LAB 设备配对 | 扫码连接 DG-LAB APP，双通道独立控制 |
| VRChat 日志监控 | 自动检测电击事件并触发设备 |
| Avatar OSC 接收 | 距离/电击/触碰三种模式，实时响应 VRChat Avatar 参数 |
| VRChat Avatar OSC 参数模式说明 | |
| `distance` | **连续模式**，OSC 值持续映射为电刺激强度，强度与参数值成比例，连续发送波形 |
| `shock` | **阈值触发模式**，OSC 值超过设定阈值时触发一次电击（持续指定时长） |
| `touch` | **导数模式**，根据触摸速度/加速度的导数（速率变化）生成电刺激波形，动态响应触摸激烈程度 |
| Chatbox 状态显示 | 头顶显示强度、剩余时间、波形名等，每行可独立开关 |
| 波形预览 | 实时动画播放，滑动窗口展示波形数据 |
| 时长累计 | 连续触发时电击时长自动叠加 |
| 安全限制 | 1秒内累计电击不超过10秒 |
| 双通道测试 | 一键测试电击，验证设备连接 |
| 参数自定义 | 电击秒数-强度映射、波形模式、强度上限均可配置 |
| 暗黑/明亮主题 | 一键切换 UI 主题 |
| 设置持久化 | 所有配置自动保存到本地 |

## 截图

![界面预览](screenshot.png)

## 使用方法

### 1. 下载

从 [Releases](https://github.com/cheesestudio/DG-LAB-VRChat-Cheese-Club/releases) 下载 `芝士郊狼控制软件.exe`，双击运行即可，无需安装。

### 2. 连接 DG-LAB APP

1. 启动软件，界面自动生成二维码
2. 打开手机上的 DG-LAB APP → 扫描二维码
3. 配对成功后自动将强度设为上限

### 3. 连接 VRChat

1. 启动 VRChat（软件会自动监控日志）
2. 软件自动启动 OSC 服务（Chatbox 端口 9000，Avatar 端口 9001）
3. 进入 VRChat 后，电击事件会自动触发设备

### 4. Chatbox 自定义

在第二列「Chatbox自定义」输入框中编辑显示内容，每行可通过复选框独立开关：

```
[芝士郊狼台球后援会]        ← 标题行
A: 0 | B: 0                 ← 强度行
剩余电击: 5秒                ← 剩余秒数（仅电击时显示）
A:挑逗2 B:信号灯            ← 波形名
我是Saob                   ← 自定义内容
QQ:757992539 | v1.1        ← 固定显示
```

### 5. 测试设备

点击「测试电击 (3秒双通道满)」按钮，验证设备是否正常工作。

---

## 开发者

### 项目结构

```
├── main.py              # 入口
├── app.py               # 应用主逻辑
├── ws_client.py         # DG-LAB WebSocket 服务器（v2 协议）
├── avatar_handler.py    # VRChat Avatar OSC 处理器
├── waveform.py          # 波形生成
├── waveform_library.py  # 预设波形库
├── log_monitor.py       # VRChat 日志监控
├── settings.py          # 设置管理
├── themes.py            # 主题配置
├── gui/                 # GUI 面板
│   ├── main_window.py
│   ├── connection_panel.py
│   ├── settings_panel.py
│   ├── mapping_panel.py
│   ├── waveform_panel.py
│   ├── osc_panel.py
│   └── console_panel.py
└── build.bat            # 构建脚本
```

### 从源码运行

```bash
pip install -r requirements.txt
python main.py
```

> 需要 Python 3.10+，websockets 库请使用 12.0 版本

### 构建 EXE

```bash
build.bat
```

### 依赖

| 库 | 用途 |
|---|---|
| websockets (==12.0) | DG-LAB WebSocket 通信 |
| python-osc | VRChat OSC 收发 |
| matplotlib | 波形预览 |
| qrcode + Pillow | 二维码生成 |

### 协议与参考

- [DG-LAB SOCKET v2 协议](https://github.com/DGLab-Project/DG-LAB-SOCKET-v2) — 与 DG-LAB 官方 APP 兼容
- [Shocking-VRChat](https://github.com/VRChatNext/Shocking-VRChat) — HTTP 接口参考（状态检测、电击触发）
- Udon 脚本参考：Ero小玉 / Cheese

### 许可

MIT License
