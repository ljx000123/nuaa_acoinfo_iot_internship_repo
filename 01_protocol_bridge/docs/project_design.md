# 项目设计文档

项目名称：物联网传输协议桥接组件开发

负责人：[姓名]

## 1. 背景

LoRa、LoRaWAN、ZigBee 等物联网设备常通过 MQTT 上传数据，而上层工业应用或边缘平台可能使用 VSOA 等服务接口进行数据查询和控制。为了实现异构协议之间的互联互通，需要设计一个协议桥接组件，完成 MQTT 与 VSOA 之间的数据转换和消息转发。

## 2. 建设目标

- 支持 MQTT 上行数据接收和解析
- 支持 MQTT payload 到 VSOA 数据模型转换
- 支持 VSOA 下行命令到 MQTT 控制消息转换
- 支持 LoRa 与 ZigBee 两类设备数据接入
- 提供配置文件、日志、测试脚本和部署说明
- 形成可演示、可复现、可验收的项目成果

## 3. 系统架构

```text
LoRa/ZigBee Device
        |
        v
MQTT Broker
        |
        v
MQTT-VSOA Bridge
  - topic subscription
  - payload validation
  - schema transform
  - logging and tests
        |
        v
VSOA Service / ADP Platform
```

下行控制流程：

```text
VSOA Client -> Bridge -> MQTT Broker -> LoRa/ZigBee Device
```

## 4. 模块设计

### 4.1 配置模块

文件：`src/bridge/config_loader.py`

负责读取 `config/bridge_config.yaml`，包括 MQTT broker、topic 模板、VSOA 服务地址和 schema 必填字段。

### 4.2 数据模型模块

文件：`src/bridge/schema.py`

定义 `DeviceData` 和 `DeviceCommand`，并完成 payload 必填字段校验。

### 4.3 转换模块

文件：`src/bridge/transformer.py`

负责：

- MQTT payload 转 VSOA 数据模型
- VSOA command 转 MQTT payload
- 根据协议和设备编号生成下行 topic

### 4.4 VSOA 适配模块

文件：`src/bridge/vsoa_adapter.py`

当前提供 `MockVsoaService` 用于本地测试。真实项目中可替换为翼辉 ADP 或 VSOA SDK 接口。

### 4.5 桥接服务模块

文件：`src/bridge/bridge_service.py`

对外提供：

- `handle_mqtt_uplink(topic, payload_text)`
- `handle_vsoa_downlink(command_payload)`

## 5. Topic 规范

上行 topic：

```text
iot/{protocol}/{device_id}/uplink
```

下行 topic：

```text
iot/{protocol}/{device_id}/downlink
```

示例：

```text
iot/lora/node-001/uplink
iot/zigbee/cc2530-001/downlink
```

## 6. Payload 规范

上行数据：

```json
{
  "protocol": "lora",
  "device_id": "node-001",
  "timestamp": "2026-07-02T10:00:00Z",
  "data": {
    "temperature": 26.4,
    "humidity": 61.2
  },
  "meta": {
    "experiment": "L5"
  }
}
```

下行命令：

```json
{
  "protocol": "zigbee",
  "device_id": "cc2530-001",
  "command": "set_led",
  "params": {
    "state": "on"
  },
  "request_id": "cmd-001"
}
```

## 7. 后续扩展

- 接入真实 MQTT broker
- 接入翼辉 VSOA SDK
- 增加断线重连机制
- 增加命令回执等待和超时处理
- 增加多设备并发测试
- 增加 LoRa/ZigBee 真实链路联调记录


