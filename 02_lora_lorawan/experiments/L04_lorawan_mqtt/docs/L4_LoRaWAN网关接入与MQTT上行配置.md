# L4：LoRaWAN 网关接入与 MQTT 上行配置

## 一、版本信息

| 项目 | 内容 |
| --- | --- |
| 模块编号 | L4 |
| 模块名称 | LoRaWAN网关接入与MQTT上行 |
| 硬件平台 | E870 LoRaWAN Hub + EoRa-S3-400TB |
| 网络服务器 | ChirpStack v4 |
| MQTT Broker | Mosquitto |
| 开发语言 | Python |

## 二、功能目标

### 2.1 主要功能

本模块实现基于 LoRaWAN 与 WiFi MQTT 双链路的数据采集系统，实现环境数据采集、无线传输以及 MQTT 数据统一接入。主要功能如下：

（1）完成 E870 LoRaWAN Hub 接入 ChirpStack 网络服务器；

（2）完成 EoRa-S3-400TB 节点 OTAA 入网；

（3）实现 LoRa 节点环境数据通过 LoRaWAN 上传；

（4）实现 ChirpStack 通过 MQTT 发布 LoRaWAN 上行数据；

（5）实现 EoRa-S3-400TB 通过 WiFi MQTT 直接上传环境数据；

（6）实现 MQTT 数据统一转发；

（7）实现后端系统通过统一 MQTT 接口获取不同链路数据；

（8）实现 Payload 解码与温湿度数据解析。

### 2.2 系统整体结构

系统包含两条数据采集链路：LoRaWAN 链路和 WiFi MQTT 链路。

#### 2.2.1 LoRaWAN 链路

```text
EoRa-S3-400TB
    |
    | LoRaWAN
    ↓
E870 LoRaWAN Hub
    |
    ↓
ChirpStack Server
    |
    ↓
T113 MQTT Broker
192.168.137.118
    |
    | mqtt_gateway_bridge.py
    ↓
PC Mosquitto
192.168.3.219
    |
    ↓
后端系统
```

该链路负责：

（1）LoRa 无线通信；

（2）网关接收节点数据；

（3）ChirpStack 设备管理；

（4）MQTT 上行数据生成；

（5）LoRa 数据统一 Topic 转发。

#### 2.2.2 WiFi MQTT 链路

```text
EoRa-S3-400TB
    |
    | WiFi MQTT
    ↓
PC Mosquitto
192.168.3.219
    |
    ↓
后端系统
```

WiFi 链路不经过 LoRaWAN Gateway Bridge。EoRa-S3-400TB 作为独立 MQTT Client，直接连接 PC 端 Mosquitto Broker，并发布环境数据。

该链路负责：

（1）WiFi 网络通信；

（2）MQTT 消息发布；

（3）环境数据实时上传。

#### 2.2.3 统一后端接口

最终后端无需访问 T113 内部网络，只需连接：

```text
MQTT Broker: 192.168.3.219:1883
```

订阅：

```text
bridge/uplink/lora/+/data
bridge/uplink/generic/eora_s3_400tb_001/data
```

即可同时获取：LoRaWAN 数据和 WiFi 数据。

## 三、系统环境

### 3.1 硬件

#### 3.1.1 LoRaWAN Gateway

| 参数 | 值 |
| --- | --- |
| 设备 | E870 LoRaWAN Hub |
| Gateway ID | 0000000000000923 |

#### 3.1.2 LoRa 节点

| 参数 | 值 |
| --- | --- |
| 设备 | EoRa-S3-400TB |
| DevEUI | 0000000000000925 |
| 工作区域 | CN470 |

#### 3.1.3 WiFi MQTT 节点

| 参数 | 值 |
| --- | --- |
| 设备 | EoRa-S3-400TB |
| 通信方式 | WiFi MQTT |
| MQTT Broker | 192.168.3.219 |
| Topic | bridge/uplink/generic/eoras3400tb_001/data |

### 3.2 系统组成

| 组件 | 说明 |
| --- | --- |
| EoRa-S3-400TB | 采集环境数据，通过 LoRaWAN 或 WiFi 上传 |
| E870 LoRaWAN Hub | 接收 LoRa 数据并上传服务器 |
| ChirpStack Server | LoRaWAN 网络服务器 |
| T113 MQTT Broker | ChirpStack 内部 MQTT 服务 |
| mqtt_gateway_bridge.py | LoRa MQTT 数据转发程序 |
| Mosquitto MQTT Broker | PC 端统一 MQTT 入口 |
| mqtt_receiver.py | MQTT 订阅与数据解析程序 |
| 后端系统 | 业务处理与数据显示 |

## 四、网络配置

### 4.1 PC WLAN

| 参数 | 值 |
| --- | --- |
| IPv4 | 192.168.3.219 |
| 网关 | 192.168.3.1 |
| 子网掩码 | 255.255.255.0 |

### 4.2 HUB

| 参数 | 值 |
| --- | --- |
| IPv4 | 192.168.137.1 |
| 子网掩码 | 255.255.255.0 |

### 4.3 E870（T113 服务器）

| 参数 | 值 |
| --- | --- |
| 接口 | eth0 |
| IP | 192.168.137.118 |
| 子网掩码 | 255.255.255.0 |
| 网关 | 192.168.137.1 |
| DNS | 8.8.8.8 |

配置文件路径：

```text
/etc/systemd/network/01-eth0.network
```

```ini
[Match]
Name=eth0

[Network]
Address=192.168.137.118/24
Gateway=192.168.137.1
DNS=8.8.8.8
```

## 五、ChirpStack 服务配置

Docker 服务列表

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| chirpstack | 8080 (REST API) / 8090 | LoRaWAN 网络服务器 |
| chirpstack-gateway-bridge | 1700 UDP | 网关桥接（UDP） |
| mosquitto | 1883 | MQTT Broker |
| postgresql | 5432 | 数据库 |
| redis | 6379 | 缓存 |

## 六、LoRaWAN MQTT Gateway Bridge 配置

`mqtt_gateway_bridge.py` 运行于 PC 端，用于连接 T113 上的 ChirpStack MQTT 服务，并将 LoRaWAN 数据转发至 PC Mosquitto。

### 6.1 数据来源

源服务器：

```text
192.168.137.118
```

源 Topic：

```text
application/+/device/+/event/up
```

### 6.2 转发目标

目标服务器：

```text
192.168.3.219
```

目标 Topic：

```text
bridge/uplink/lora/lora_env_01/data
```

## 七、Gateway 接入验证

### 7.1 Web 界面查看

ChirpStack → Gateway → Online

### 7.2 日志查看

命令：

```bash
docker logs chirpstack-chirpstack-gateway-bridge-1
```

输出：

```text
gateway connected
```

## 八、节点入网验证

节点成功 Join 后，ChirpStack 产生上行数据：

原始 Topic：

```text
application/{applicationID}/device/{devEUI}/event/up
```

例如：

```text
application/3ed92fba-9e06-4b8e-ad41-54927a0fa89d/device/0000000000000925/event/up
```

经过 mqtt_gateway_bridge.py 转发为：

```text
bridge/uplink/lora/lora_env_01/data
```

## 九、MQTT 配置

### 9.1 MQTT Broker 信息

当前系统采用 PC 端 Mosquitto 作为统一 MQTT 数据入口。

| 参数 | 值 |
| --- | --- |
| 协议 | MQTT |
| 地址 | 192.168.137.118 |
| 端口 | 1883 |
| 用户名 | 无 |
| 密码 | 无 |

说明：

（1）T113 内部的 MQTT Broker 仅用于 ChirpStack 数据发布；

（2）PC Mosquitto 用于统一接收 LoRaWAN 与 WiFi MQTT 数据；

（3）后端系统只需要连接 PC Mosquitto 即可。

### 9.2 MQTT Topic 说明

系统当前采用统一 Topic 命名规则：

```text
bridge/uplink/{type}/{device_id}/data
```

| 字段 | 含义 |
| --- | --- |
| bridge | 统一数据转发标识 |
| uplink | 上行数据 |
| type | 数据来源类型 |
| device_id | 设备编号 |
| data | 数据消息 |

#### 9.2.1 LoRaWAN Topic

Topic：`bridge/uplink/lora/lora_env_01/data`

数据来源：

```text
EoRa-S3-400TB → E870 Gateway → ChirpStack → mqtt_gateway_bridge.py → PC Mosquitto
```

说明：该 Topic 表示经过 LoRaWAN 网络上传的数据。

#### 9.2.2 WiFi MQTT Topic

Topic：`bridge/uplink/generic/eora_s3_400tb_001/data`

数据来源：

```text
EoRa-S3-400TB → WiFi MQTT → PC Mosquitto (192.168.3.219)
```

说明：该 Topic 表示设备通过 WiFi 网络直接上传的数据。

### 9.3 MQTT 订阅方式

后端或测试程序订阅：

```text
bridge/uplink/lora/+/data
bridge/uplink/generic/+/data
```

即可同时接收：LoRaWAN 节点数据和 WiFi MQTT 数据。

## 十、MQTT 数据格式

系统中 MQTT 数据均采用 JSON 格式。

### 10.1 LoRaWAN MQTT 数据格式

LoRaWAN 数据经过 ChirpStack 解析后，由 MQTT Gateway Bridge 转发。

Topic：`bridge/uplink/lora/lora_env_01/data`

示例：

```json
{
  "time": "2026-07-16T06:05:23.807156452+00:00",
  "deviceInfo": {
    "devEui": "0000000000000925",
    "deviceName": "Ebyte Test Device 470"
  },
  "devAddr": "01baa6a7",
  "data": "ABSd2tGAABT2gQABCQI6AQ==",
  "rxInfo": [
    {
      "gatewayId": "0000000000000923",
      "rssi": -27,
      "snr": 14.0
    }
  ]
}
```

| 字段 | 说明 |
| --- | --- |
| deviceInfo | 设备信息 |
| devAddr | LoRa 设备地址 |
| data | Base64 编码 Payload |
| rxInfo | 网关接收信息 |
| rssi | 信号强度 |
| snr | 信噪比 |

### 10.2 WiFi MQTT 数据格式

WiFi 数据由 EoRa-S3-400TB 直接发布。

Topic：`bridge/uplink/generic/eora_s3_400tb_001/data`

示例：

```json
{
  "device_id": "eora_s3_400tb_001",
  "name": "eora_s3_400tb_001",
  "type": "multi",
  "status": "online",
  "source": "generic",
  "timestamp": 1783329001000,
  "temperature": 26.2,
  "humidity": 55.2,
  "signal": -61,
  "raw": {
    "dev_eui": "0000000000000925",
    "boot_id": 3302695251,
    "seq": 2,
    "send_time_ms": 496501,
    "wifi_retry_count": 0,
    "link": "wifi"
  }
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| device_id | 设备编号 |
| temperature | 温度 |
| humidity | 湿度 |
| signal | WiFi 信号强度 |
| seq | 数据序号 |
| boot_id | 设备启动编号 |
| wifi_retry_count | WiFi 重传次数 |
| link | 通信链路类型 |

## 十一、Payload 解析协议

LoRa 节点应用层 Payload 长度：16 Bytes

### 11.1 字段定义

| Byte | 字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| 0-1 | seq (packetSeq) | uint16 | 数据序号 |
| 2-5 | boot_id (bootId) | uint32 | 启动编号 |
| 6-9 | sendtimems (sendTimeMs) | uint32 | 运行时间 (ms) |
| 10 | retry_count (retryCount) | uint8 | LoRaWAN 应用重传次数 |
| 11-12 | temperature | int16 | 温度 × 10 |
| 13-14 | humidity | uint16 | 湿度 × 10 |
| 15 | flags | uint8 | 状态标志 |

### 11.2 flags 位定义

| Bit | 名称 | 说明 |
| --- | --- | --- |
| bit0 | joined | 是否成功入网 |
| bit3 | application retry | 应用层重传 |

### 11.3 数据解析公式

（1）温度：`temperature = raw_temperature / 10`（℃）

（2）湿度：`humidity = raw_humidity / 10`（%）

## 十二、Payload 解析示例

### 12.1 原始 Base64 数据

```text
AEGcSB0jAD7kbQABCQIrAQ==
```

### 12.2 Base64 解码 HEX

```text
00029ddad180000267df000106022801
```

### 12.3 解析结果

| 字段 | HEX | 结果 |
| --- | --- | --- |
| seq | 0002 | 2 |
| boot_id | 9ddad180 | 0x9ddad180 |
| sendtimems | 000267df | 157663ms |
| retry_count | 00 | 0 |
| temperature | 0228 | 552 → 26.2℃ |
| humidity | 0228 | 552 → 55.2% |
| flags | 01 | joined=True |

## 十三、MQTT 接收与解析流程

系统整体数据处理流程如下：

```text
LoRaWAN 链路                          WiFi MQTT链路
EoRa-S3-400TB                         EoRa-S3-400TB
    | LoRaWAN                             | WiFi
    ↓                                     ↓
E870 LoRaWAN Hub                      PC Mosquitto
    |                                  (192.168.3.219)
    ↓                                     ↑
ChirpStack                               |
    |                                    |
    ↓                                    |
mqtt_gateway_bridge.py -------------------+
    |
    ↓
PC Mosquitto (192.168.3.219)
    |
    ↓
mqtt_receiver.py
    |
    ↓
JSON解析
    |
    ↓
Payload解析
    |
    ↓
温湿度数据输出

说明:
1. LoRaWAN链路: 数据经过网关和ChirpStack,由mqtt_gateway_bridge.py转发到PC Mosquitto。
2. WiFi MQTT链路: 设备通过WiFi直接将数据发布到PC Mosquitto。
3. PC Mosquitto统一接收两条链路的数据,后续由mqtt_receiver.py进行解析处理。
```

## 十四、MQTT 验证代码

### 14.1 文件

```text
mqtt_receiver.py
```

### 14.2 功能

mqtt_receiver.py 主要实现：

（1）连接 PC Mosquitto；

（2）订阅统一 MQTT Topic；

（3）判断数据来源；

（4）解析 WiFi JSON 数据；

（5）解析 LoRaWAN JSON 数据；

（6）Base64 解码；

（7）Payload 字段解析；

（8）输出环境参数。

### 14.3 MQTT 订阅 Topic

代码配置：

```python
MQTT_TOPICS = [
    ("bridge/uplink/lora/+/data", 1),
    ("bridge/uplink/generic/eora_s3_400tb_001/data", 1)
]
```

### 14.4 输出示例

```text
正在连接MQTT...
MQTT连接成功
订阅Topic:
  bridge/uplink/lora/+/data
  bridge/uplink/generic/eora_s3_400tb_001/data

========================
Topic:
bridge/uplink/lora/lora_env_01/data

========== LoRaWAN数据 ==========
Device ID: lora_env_01
DevEUI: 0000000000000925
设备: Ebyte Test Device 470
时间: 2026-07-16T07:50:21.952896917+00:00
Gateway: 0000000000000923
RSSI: -25
SNR: 14.0
Base64: AFBNg2t9AEz/GwABCQI6AQ==
HEX: 00504d836b7d004cff1b000109023a01

======= LoRa解析结果 =======
温度: 26.5 ℃
湿度: 57.0 %
序号: 80
Boot ID: 0x4d836b7d
LoRa重传: 0
Joined: True
App Retry: False
============================

========================
Topic:
bridge/uplink/generic/eora_s3_400tb_001/data

========== WiFi S3数据 ==========
Device ID: eora_s3_400tb_001
Name: eora_s3_400tb_001
Type: multi
Status: online
Source: generic
Timestamp: 1784188222251
Temperature: 26.5 ℃
Humidity: 57.0 %
Signal: -63

Raw:
DevEUI: 0000000000000925
Boot ID: 1300458365
Seq: 80
WiFi Retry: 0
Link: wifi
============================
```

## 十五、系统运行总结

本模块最终实现：

（1）EoRa-S3-400TB 通过 LoRaWAN 完成远距离无线数据传输；

（2）E870 Gateway 完成 LoRa 无线信号接收；

（3）ChirpStack 完成 LoRaWAN 网络管理；

（4）mqtt_gateway_bridge.py 实现 LoRa MQTT 数据跨网络转发；

（5）EoRa-S3-400TB 通过 WiFi MQTT 直接上传数据；

（6）PC Mosquitto 作为统一 MQTT 入口；

（7）mqtt_receiver.py 完成双链路数据解析；

（8）后端系统通过统一 Topic 获取环境监测数据。

最终系统结构：

```text
LoRaWAN
EoRa-S3-400TB
    |
    ↓
E870 Gateway
    |
    ↓
ChirpStack
    |
    ↓
mqtt_gateway_bridge.py
    |
    ↓
PC Mosquitto ←--- WiFi MQTT
    |              EoRa-S3-400TB
    |
    ↓
后端业务系统
```
