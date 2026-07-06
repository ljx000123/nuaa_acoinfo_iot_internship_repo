# 测试说明文档

负责人：[姓名]

## 1. 测试目标

验证 MQTT 与 VSOA 协议桥接组件是否能够完成上行数据转换、下行命令转换、异常输入处理和基础日志记录，保证项目成果可运行、可复现、可验收。

## 2. 测试环境

- Python 3.10+
- pytest
- PyYAML
- paho-mqtt
- 可选：本地 MQTT broker
- 可选：ACOINFO ADP / VSOA SDK

## 3. 测试范围

| 编号 | 测试项 | 说明 | 优先级 |
| --- | --- | --- | --- |
| T01 | MQTT 上行 JSON 解析 | 校验合法 JSON payload | 高 |
| T02 | 必填字段校验 | protocol、device_id、timestamp、data | 高 |
| T03 | LoRa 上行转换 | LoRa payload 转 VSOA 数据模型 | 高 |
| T04 | ZigBee 上行转换 | ZigBee payload 转 VSOA 数据模型 | 高 |
| T05 | VSOA 下行转换 | VSOA 命令转 MQTT payload | 高 |
| T06 | 下行 topic 生成 | 按协议和设备编号生成 topic | 高 |
| T07 | 非法 payload | 缺字段、data 类型错误、JSON 错误 | 中 |
| T08 | 日志检查 | 运行日志可追踪输入输出 | 中 |
| T09 | 真实设备联调 | 接入 LoRa/ZigBee 真实链路 | 高 |
| T10 | 交叉复现 | 非作者按文档完成运行 | 高 |

## 4. 运行方式

本地 demo：

```bash
python scripts/demo_local_bridge.py
```

自动化测试：

```bash
pytest
```

Windows PowerShell：

```powershell
scripts\run_tests.ps1
```

## 5. 验收标准

- 上行 LoRa payload 可转换为 VSOA 数据模型
- 上行 ZigBee payload 可转换为 VSOA 数据模型
- 下行 VSOA command 可转换为 MQTT downlink topic 和 payload
- 异常 payload 能给出明确错误信息
- 日志文件能够记录关键输入、输出和错误
- README 能指导其他成员完成复现


