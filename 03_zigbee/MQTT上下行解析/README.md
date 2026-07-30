# Zigbee MQTT网关系统 - MQTT原生版本

## 架构说明

本版本使用Zigbee网关的内置MQTT功能，无需TCP连接。系统架构：

```
Zigbee设备 <--无线--> Zigbee网关 <--MQTT--> MQTT Broker <--MQTT--> 应用程序
                          |                                        |
                          |                                        |
                  (发布原始HEX帧)                          (订阅并解析/控制)
```

### 数据流向

**上行数据流**：
1. Zigbee设备 → 网关（无线）
2. 网关 → MQTT Broker：发布原始HEX帧到 `zigbee/gw/uplink`
3. mqtt_bridge.py：订阅 `zigbee/gw/uplink`，解析后发布JSON到 `bridge/uplink/zigbee/{device_id}/data`
4. 应用程序：订阅 `bridge/uplink/zigbee/+/data` 接收传感器数据
5. link_monitor.py：订阅数据主题，计算链路质量，发布状态到 `bridge/uplink/zigbee/{device_id}/status`

**下行控制流**：
1. 应用程序 → MQTT Broker：发布JSON命令到 `bridge/downlink/zigbee/{device_id}/set`
2. mqtt_downlink.py：订阅 `bridge/downlink/#`，转换为HEX帧并发布到 `zigbee/gw/downlink`
3. 网关订阅 `zigbee/gw/downlink`，接收HEX帧并通过无线发送给Zigbee设备


## 网关MQTT配置

### 网关参数设置

1. 访问网关Web配置页面（通常是 `http://192.168.3.7`）
2. 进入MQTT设置页面，配置如下：

| 参数 | 值 | 说明 |
|------|-----|------|
| MQTT服务器 | `192.168.200.169` | EMQX Broker地址 |
| MQTT端口 | `1883` | 标准MQTT端口 |
| 协议版本 | `MQTT 3.1.1` | 协议版本 |
| 客户端ID | `zigbee_gateway_01` | 网关标识 |
| 用户名 | （留空） | 本地broker无需认证 |
| 密码 | （留空） | 本地broker无需认证 |
| 保活时间 | `60` 秒 | Keep-alive间隔 |
| 清除会话 | `是` | Clean Session |
| **发布主题** | `zigbee/gw/uplink` | 网关上行数据发布主题 |
| 发布QoS | `1` | 至少一次送达 |
| 发布格式 | `HEX字符串` | 原始帧转16进制字符串 |
| **订阅主题** | `zigbee/gw/downlink` | 网关下行控制订阅主题 |
| 订阅QoS | `1` | 至少一次送达 |

3. 保存配置并重启网关


## 程序说明

### 1. mqtt_bridge.py - 上行数据桥接器

**功能**：
- 订阅网关发布的原始HEX帧（`zigbee/gw/uplink`）
- 解析Ebyte帧格式，提取设备地址、RSSI、LQI、ZCL数据
- 识别传感器类型（P00 ADC、Terminal1 MQ2+PIR、Environment DHT11+光敏+气压）
- 发布JSON格式到 `bridge/uplink/zigbee/{device_id}/data`

**启动**：
```bash
python mqtt_bridge.py
```

**发布消息格式**：
```json
{
  "device_id": "0xB25B",
  "timestamp": 1721800000,
  "rssi": -65,
  "lqi": 255,
  "data": {
    "sensor_type": "environment",
    "temperature": 25.3,
    "humidity": 60.2,
    "light_value": 512,
    "pressure": 1013,
    "sequence": 42
  }
}
```


### 2. mqtt_downlink.py - 下行控制处理器

**功能**：
- 订阅应用层控制命令（`bridge/downlink/#`）
- 支持设备别名（`relay` → `0xB25B`，`led` → `0xC38F`）
- 转换JSON命令为Ebyte帧格式
- 发布HEX字符串到 `zigbee/gw/downlink`

**启动**：
```bash
python mqtt_downlink.py
```

**控制命令格式**：
```json
// 透明传输方式（推荐）
{
  "device_id": "relay",
  "params": {
    "data": "01"
  }
}

// 标准ON/OFF方式
{
  "device_id": "0xC38F",
  "params": {
    "state": "on"
  }
}
```

**发布主题**：
- `bridge/downlink/zigbee/{device_id}/set`


### 3. link_monitor.py - 链路质量监控

**功能**：
- 订阅 `bridge/uplink/zigbee/+/data`
- 计算每设备的丢包率、RSSI统计、吞吐量、抖动
- 检测设备离线（30秒无数据）
- 发布状态到 `bridge/uplink/zigbee/{device_id}/status`
- 实时控制台显示
- 可选CSV日志记录

**启动**：
```bash
python link_monitor.py
```

**状态消息格式**：
```json
{
  "device_id": "0xB25B",
  "status": "online",
  "age_s": 2.5,
  "received": 120,
  "lost": 3,
  "loss_rate_pct": 2.44,
  "rssi_last": -65,
  "rssi_avg": -67,
  "rssi_min": -72,
  "msg_rate": 1.8,
  "byte_rate": 45.2,
  "avg_interval_ms": 550,
  "jitter_ms": 15.3
}
```


## MQTT主题层次

```
zigbee/gw/uplink              # 网关发布：原始HEX帧
zigbee/gw/downlink            # 网关订阅：原始HEX帧

bridge/uplink/zigbee/+/data   # 应用订阅：设备传感器数据（JSON）
bridge/uplink/zigbee/+/status # 应用订阅：设备链路状态（JSON）
bridge/downlink/zigbee/+/set  # 应用发布：设备控制命令（JSON）
```


## 依赖安装

```bash
pip install paho-mqtt
```


## 使用流程

### 1. 启动EMQX Broker

```bash
cd E:\emqx\emqx-5.3.2\bin
emqx.cmd start
```

访问管理界面：http://192.168.200.169:18083
- 用户名：`admin`
- 密码：`public`


### 2. 配置Zigbee网关

按照上述"网关MQTT配置"章节设置网关参数


### 3. 启动系统组件

**终端1 - 上行桥接器**：
```bash
cd "d:\Zigbee项目\MQTT版本"
python mqtt_bridge.py
```

**终端2 - 下行处理器**：
```bash
cd "d:\Zigbee项目\MQTT版本"
python mqtt_downlink.py
```

**终端3 - 链路监控**：
```bash
cd "d:\Zigbee项目\MQTT版本"
python link_monitor.py
```


### 4. 测试

**使用MQTTX客户端测试**：

1. 订阅传感器数据：
   - 主题：`bridge/uplink/zigbee/+/data`
   - QoS：1

2. 订阅链路状态：
   - 主题：`bridge/uplink/zigbee/+/status`
   - QoS：1

3. 发送控制命令：
   - 主题：`bridge/downlink/zigbee/relay/set`
   - QoS：1
   - 消息：`{"device_id":"relay","params":{"data":"01"}}`


## 设备信息

| 设备名称 | 短地址 | 别名 | 传感器类型 | 说明 |
|----------|--------|------|-----------|------|
| 继电器板 | 0xB25B | relay | 环境传感器 | DHT11温湿度、光敏、气压 |
| LED板 | 0xC38F | led | Terminal1 | MQ2烟雾、PIR人体红外 |
| P00模块 | - | - | P00 ADC | 模拟电压采集 |


## 与TCP版本的区别

| 特性 | TCP版本 | MQTT版本 |
|------|---------|----------|
| 网关连接 | TCP Socket 192.168.3.7:8887 | MQTT Pub/Sub |
| 数据格式 | 原始字节流 | HEX字符串 |
| 下行确认 | 需等待网关ACK（3秒超时） | MQTT QoS保证送达 |
| 网关配置 | 透传模式 | MQTT模式 |
| 复杂度 | 需维护TCP连接状态 | MQTT自动重连 |
| 扩展性 | 单点连接 | 多客户端订阅 |


## 故障排查

### 网关无数据上报

1. 检查网关MQTT配置是否正确
2. 确认网关能连接到EMQX（查看EMQX客户端列表）
3. 使用MQTTX订阅 `zigbee/gw/uplink` 查看原始数据
4. 检查mqtt_bridge.py是否运行并成功订阅

### 控制命令无响应

1. 检查mqtt_downlink.py是否运行
2. 使用MQTTX订阅 `zigbee/gw/downlink` 查看发送的HEX帧
3. 确认设备ID或别名是否正确
4. 检查网关是否订阅了下行主题

### 链路监控无数据

1. 确认mqtt_bridge.py正常发布数据
2. 检查link_monitor.py订阅主题是否正确
3. 使用MQTTX确认 `bridge/uplink/zigbee/+/data` 有消息


## 注意事项

1. **网关只能工作在TCP模式或MQTT模式之一**，不能同时启用
2. **本版本不兼容TCP版本的网关配置**，需重新配置网关
3. 网关发布的HEX字符串不含空格，示例：`5503000F00B25B...`
4. 控制命令中 `data` 字段为HEX字符串，不含 `0x` 前缀
5. 所有MQTT消息使用QoS 1保证送达，不使用retain
6. 设备短地址可能在重新入网后改变，使用别名映射来应对


## 参考文档

- [overall_experiment_rules.md](overall_experiment_rules.md) - 完整的实验规范和接口定义
- Ebyte E180-DTU Z20-ETH网关用户手册
- MQTT 3.1.1协议规范
