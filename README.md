# 芝士郊狼控制软件

VRChat + DG-LAB 设备联动控制工具，属于**芝士郊狼台球后援会**（[VRC群组链接 CHEESE.2410](https://vrc.group/CHEESE.2410)，QQ群: 757992539）。

---

## 目录

- [功能一览](#功能一览)
- [快速开始](#快速开始)
- [Avatar 参数说明](#avatar-参数说明)
- [Chatbox 自定义](#chatbox-自定义)
- [HTTP API](#http-api供-vrchat-udon-调用)
- [常见问题排查](#常见问题排查)
- [开发者](#开发者)

---

## 功能一览

| 功能 | 说明 |
|------|------|
| DG-LAB 设备配对 | 扫码连接 DG-LAB APP，双通道独立控制 |
| VRChat 日志监控 | 自动检测电击事件并触发设备 |
| Avatar OSC 接收 | 距离/电击/触碰三种模式，实时响应 VRChat Avatar 参数 |
| Chatbox 状态显示 | 头顶显示强度、剩余时间、波形名等，每行可独立开关 |
| 波形预览 | 实时动画播放，滑动窗口展示波形数据 |
| 时长累计 | 连续触发时电击时长自动叠加 |
| 安全限制 | 1秒内累计电击不超过10秒 |
| 双通道测试 | 一键测试电击，验证设备连接 |
| 参数自定义 | 电击秒数-强度映射、波形模式、强度上限均可配置 |
| 暗黑/明亮主题 | 一键切换 UI 主题 |
| 设置持久化 | 所有配置自动保存到本地 |

---

## 截图

![界面预览](screenshot.png)

---

## 快速开始

### 1. 下载运行

从 [Releases](https://github.com/cheesestudio/DG-LAB-VRChat-Cheese-Club/releases) 下载 `芝士郊狼控制软件.exe`，双击运行即可，无需安装。

### 2. 连接 DG-LAB APP

1. 启动软件，界面自动生成二维码
2. 打开手机上的 DG-LAB APP → 扫描二维码
3. 配对成功后自动将强度设为上限

### 3. 连接 VRChat

1. 在 VRChat 中开启 OSC：`Action Menu → Osc → Enabled`
2. 软件自动启动 OSC 服务（Avatar 端口 `9001`，Chatbox 端口 `9000`）
3. 进入 VRChat 后，Avatar 参数变化会实时触发设备

### 4. 测试设备

点击「测试电击 (3秒双通道满)」按钮，验证设备是否正常工作。

---

## Avatar 参数说明

### 监听的 OSC 地址

软件在 `9001` 端口监听 VRChat 发来的 Avatar 参数，每条消息根据配置的地址匹配到对应通道和模式。

#### 通道 A 默认监听地址

| 地址 | 说明 |
|------|------|
| `/avatar/parameters/pcs/contact/enterPass` | 进入传送门时触发（bool） |
| `/avatar/parameters/Shock/TouchAreaA` | 触摸区域 A（float 0-1） |
| `/avatar/parameters/Shock/TouchAreaC` | 触摸区域 C（float 0-1） |
| `/avatar/parameters/Shock/wildcard/*` | 所有 Shock 开头的参数（通配符） |

#### 通道 B 默认监听地址

| 地址 | 说明 |
|------|------|
| `/avatar/parameters/pcs/contact/enterPass` | 进入传送门时触发（bool） |
| `/avatar/parameters/Shock/TouchAreaB` | 触摸区域 B（float 0-1） |
| `/avatar/parameters/Shock/TouchAreaC` | 触摸区域 C（float 0-1） |
| `/avatar/parameters/lms-penis-proximityA*` | 距离感应参数 A（通配符） |

### 参数模式说明

| 模式 | 行为 |
|------|------|
| `distance`（距离/连续） | OSC 值持续映射为电刺激强度，强度与参数值成比例，连续发送波形 |
| `shock`（电击） | OSC 值超过设定阈值时触发一次电击（持续指定时长） |
| `touch`（触感/导数） | 根据触摸速度/加速度的导数（速率变化）生成电刺激波形，动态响应触摸激烈程度 |

### 给 Avatar 添加触发器（Avatar 3.0 / AV3）

以下以 **Avatar 3.0（AV3）+ 触摸触发器（Touch Sender）** 为例，说明如何让你的 Avatar 向本软件发送 OSC 参数。

> 提示：以下步骤需要你会改模，通用步骤是：**在 Avatar 上配置 OSC 参数的发送地址和类型，值通常为 float 0~1**。

#### 步骤 1：在 Avatar 上找到或创建 OSC 参数

1. 将 Avatar 上传到 VRChat
2. 进入 VRChat，使用该 Avatar(屁话)
3. 打开 `Action Menu → Osc`（需要先开启 OSC）
4. 点击「Debug」进入 OSC 调试界面，可看到所有可用的参数

#### 步骤 2：编辑 OSC 配置文件

OSC 配置保存在本地文件中，路径类似：

```
C:\Users\<你的用户名>\AppData\LocalLow\VRChat\VRChat\OSC\<你的用户ID>\Avatars\<AvatarID>.json
```

**方法 A：手动编辑配置**

1. 打开上述 JSON 文件
2. 找到你要触发的参数，在 `input` 中添加地址和类型：

```json
{
  "name": "Shock",
  "input": {
    "address": "/avatar/parameters/Shock/TouchAreaA",
    "type": "Float"
  }
}
```

3. 保存文件，重新进入游戏使配置生效

**方法 B：通过触摸触发器（推荐）**

1. 使用支持 AV3 的 Avatar（如内置了触摸触发器的 Avatar）
2. 在 Avatar 的触摸区域挂载 `OSC Touch Sender` 组件（VRChat SDK 内置）
3. 设置发送地址为 `/avatar/parameters/Shock/TouchAreaA`
4. 设置类型为 `Float`
5. 当玩家触摸该区域时，Avatar 自动发送 OSC 值（0~1）到本软件

#### 步骤 3：验证参数是否被接收

1. 启动本软件，点击「连接」按钮
2. 在 VRChat 中触发该参数（如触摸 Avatar 区域）
3. 查看软件右侧「接收参数」面板，应该能看到类似：
   ```
   /avatar/parameters/Shock/TouchAreaA: 0.75
   ```
4. 如果有反应但设备没触发，检查通道 A 的模式是否为 `distance`/`shock`/`touch` 中的合适模式

#### 常见问题

- **参数收不到**：确认 OSC 已开启（`Action Menu → Osc → Enabled`），确认软件和 VRChat 在同一台电脑上，确认端口 9001 没有被占用
- **设备不响应**：检查软件是否已连接 DG-LAB APP（看连接面板状态），检查通道模式是否正确
- **通配符不生效**：部分通配符格式可能不被 python-osc 完整支持，优先使用精确地址

---

## Chatbox 自定义

在第二列「Chatbox自定义」输入框中编辑显示内容，每行可通过复选框独立开关：

```
[芝士郊狼台球后援会]        ← 标题行
A: 0 | B: 0                 ← 强度行
剩余电击: 5秒                ← 剩余秒数（仅电击时显示）
A:挑逗2 B:信号灯            ← 波形名
我是Saob                   ← 自定义内容
QQ:757992539 | v1.1        ← 固定显示
```

---

## HTTP API（供 VRChat Udon 调用）

软件在端口 `8800` 提供了 HTTP 接口，可被 VRChat 中的 Udon 程序调用：

| 接口 | 说明 | 示例 |
|------|------|------|
| `GET /api/v1/status` | 查询设备连接状态 | `http://localhost:8800/api/v1/status` |
| `GET /api/v1/shock/A/<秒数>` | 触发通道 A 电击 | `http://localhost:8800/api/v1/shock/A/5` |
| `GET /api/v1/shock/B/<秒数>` | 触发通道 B 电击 | `http://localhost:8800/api/v1/shock/B/3` |
| `GET /api/v1/shock/all/<秒数>` | 触发双通道电击 | `http://localhost:8800/api/v1/shock/all/10` |
| `GET /api/v1/sendwave/<通道>/<重复>/<波形数据>` | 发送自定义波形 | `http://localhost:8800/api/v1/sendwave/A/10/0A0A0A0A64646464` |

> Udon 中使用 `UnityEngine.WWW` 或 `VRCWebProxy` 发送 HTTP 请求即可触发电击。

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
├── http_server.py       # HTTP 服务器（ShockingManager 兼容）
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

> 注意：仅用于 Avatar 的 touch 模式数学计算（求导/加速度），不需要 CUDA/FFT 等扩展功能。

### 协议与参考

- [DG-LAB SOCKET v2 协议](https://github.com/DGLab-Project/DG-LAB-SOCKET-v2) — 与 DG-LAB 官方 APP 兼容
- [Shocking-VRChat](https://github.com/VRChatNext/Shocking-VRChat) — HTTP 接口参考
- [VRChat OSC 文档](https://docs.vrchat.com/docs/osc-overview) — 官方 OSC 说明
- Udon 脚本参考：Ero小玉 / Cheese

## 常见问题排查

### DG-LAB APP 连接失败

| 原因 | 排查方法 | 解决方案 |
|------|---------|---------|
| 手机和电脑不在同一网络 | 检查手机连接的 WiFi 与电脑网络是否相同 | 确保手机和电脑连接同一个局域网（同一 WiFi 或有线网络） |
| 端口被占用 | 在软件控制台查看是否报错 `端口已被占用` | 关闭占用端口的程序（如其他 DG-LAB 软件），或在设置中更换端口 |
| 防火墙拦截 | 检查防火墙是否阻止了软件的网络连接 | 将软件添加至防火墙白名单，或暂时关闭防火墙测试 |
| 二维码无法扫码 | 二维码中的 IP 是否为正确的局域网 IP | 检查软件显示的本机 IP 是否与手机网络一致，必要时手动指定 |

### VRChat Avatar 参数无响应

| 原因 | 排查方法 | 解决方案 |
|------|---------|---------|
| OSC 未开启 | 在 VRChat 中检查 `Action Menu → Osc → Enabled` 是否开启 | 点击开启 OSC |
| Avatar OSC 端口被占用 | 在软件控制台查看 Avatar OSC 状态是否为红色 | 更换 Avatar 端口（如改为 9002）并重启连接 |
| 参数地址不匹配 | 查看软件右侧「接收参数」面板是否有数据更新 | 确认 Avatar 中配置的 OSC 地址与软件设置中的监听地址一致 |
| 通配符不生效 | 精确地址可收到但通配符收不到 | 改用精确地址替代通配符（如 `/avatar/parameters/Shock/TouchAreaA`） |
| Avatar 未发布 | OSC 配置文件仅在 Avatar 发布后生效 | 将 Avatar 发布后再进入游戏 |

### Chatbox 端口冲突（面捕软件）

当同时使用 VRCFaceTracking 等面捕软件时，VRCFaceTracking 可能会失效或 Chatbox 不显示。原因是两个软件同时向 VRChat 的 9000 端口发送 OSC 数据，但 VRChat 只允许单连接。

把面捕的监听端口随便改一下就行了(面捕只需要发送就能正常用),如果你真的需要用到这个功能看下面

**解决方案：使用 osc-repeater 分离 Chatbox**

1. 下载 [osc-repeater](https://github.com/CyCoreSystems/osc-repeater)
2. 在 osc-repeater 同目录创建 `config.yaml`，内容如下：

```yaml
listenPorts:
  - 9000
targets:
  - "127.0.0.1:9010"
  - "127.0.0.1:9020"
```

3. 将本软件 Chatbox 端口改为 `9010`
4. 将 面捕软件 端口改为 `9020`
4. 按顺序启动：osc-repeater → 本软件 → VRChat

### Chatbox 不显示状态

| 原因 | 排查方法 | 解决方案 |
|------|---------|---------|
| VRChat Chatbox OSC 端口不对 | 确认软件 Chatbox 端口为 `9000` | 检查软件设置中 Chatbox 端口是否为 VRChat 接收端口 |
| Chatbox 功能未开启 | 软件设置中「Chatbox显示行」全部取消勾选 | 勾选至少一行显示内容 |
| 网络配置问题 | 电脑有多个网络适配器（虚拟机、VPN 等） | 确保 VRChat 发送 OSC 的目标 IP 为本机局域网 IP |
| VRCFaceTracking 抢占端口 | VRCFaceTracking 先占用了 9000 | 使用 osc-repeater 分离端口 |
