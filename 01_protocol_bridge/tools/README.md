# tools/ — 开发与调试工具

## 工具列表

### sim_device.py — MQTT 设备模拟器

模拟 LoRa/Zigbee 设备通过 MQTT 上报数据，用于离线测试（无需真实设备）。

```bash
python tools/sim_device.py
```

可配置参数：设备类型、上报间隔、传感器数据范围。

### send_downlink.py — 下行命令发送脚本

向 bridge 发送 RPC 下行命令，用于手动验证下行链路。

```bash
python tools/send_downlink.py --device lora-node-01 --action led_on
```

### verify_e2e.py — 端到端验证脚本

自动化验证完整数据链路：
1. 模拟设备上报
2. 等待上行处理
3. 发送下行命令
4. 验证回执
5. 输出测试报告

```bash
python tools/verify_e2e.py
```

### mqtt_monitor.py — CLI MQTT 监视器

订阅指定 MQTT topic 并实时打印消息内容。

```bash
python tools/mqtt_monitor.py
```

### mqtt_test.py — MQTT 连接测试

快速验证 MQTT Broker 连接可用性。

```bash
python tools/mqtt_test.py --broker 192.168.200.221 --port 1883
```

### vsoa_monitor.py — VSOA 事件监视器

连接 VSOA Server，订阅 `/device/update` 和 `/bridge/event`，实时显示设备状态变化。

```bash
python tools/vsoa_monitor.py
```

### start_terminals.ps1 — 一键多终端启动

自动打开多个 PowerShell 终端窗口，分别运行：
- Bridge 主服务
- MQTT 监视器
- 设备模拟器
- 端到端验证

```powershell
.\tools\start_terminals.ps1
```

### python38_smoke.py — Python 3.8 兼容性验证

验证所有模块在 Python 3.8 环境下可正常导入和运行。

```bash
python tools/python38_smoke.py
```

### _test_publish.py — 内部测试辅助

用于调试 VSOA publish 功能的内部脚本（开发用）。
