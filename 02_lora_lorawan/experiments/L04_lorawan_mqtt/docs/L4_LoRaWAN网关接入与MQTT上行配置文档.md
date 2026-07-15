# LoRaWAN 网关接入与 MQTT 上行配置

## 一、版本信息

| 项目 | 内容 |
|------|------|
| 模块编号 | L4 |
| 模块名称 | LoRaWAN网关接入与MQTT上行 |
| 硬件平台 | E870 LoRaWAN Hub + EoRa-S3-400TB |
| 网络服务器 | ChirpStack v4 |
| MQTT Broker | Mosquitto |
| 开发语言 | Python |

## 二、功能目标

### 2.1 主要功能

1. LoRaWAN 网关接入 ChirpStack 网络服务器
2. LoRa 节点完成入网
3. 网关接收节点上行数据
4. ChirpStack 通过 MQTT 发布设备数据
5. 解析 MQTT Payload 中的业务数据
6. 为后端系统提供标准 MQTT 数据接口

### 2.2 整体数据流

```text
LoRa节点
(EoRa-S3-400TB)
      |
      | LoRaWAN
      ↓
LoRaWAN Hub
(E870)
      |
      | UDP Packet Forwarder
      ↓
ChirpStack Gateway Bridge
      |
      | MQTT
      ↓
Mosquitto Broker
      |
      ↓
Python解析程序/后端服务
```

图1 系统数据流

## 三、系统环境

### 3.1 硬件

#### 3.1.1 LoRaWAN Gateway

| 参数 | 值 |
|------|------|
| 设备 | E870 LoRaWAN Hub |
| Gateway ID | 0000000000000923 |

#### 3.1.2 LoRa 节点

| 参数 | 值 |
|------|------|
| 设备 | EoRa-S3-400TB |
| DevEUI | 0000000000000925 |
| 工作区域 | CN470 |

### 3.2 系统组成

| 组件 | 说明 |
|------|------|
| EoRa-S3-400TB LoRa 节点 | 采集环境数据，通过 LoRaWAN 上传 |
| E870 LoRaWAN 工业网关 | 接收 LoRa 数据并转发至服务器 |
| HUB 设备 | 提供网关网络接入 |
| ChirpStack Server | 负责 LoRaWAN 设备管理和 MQTT 数据发布 |
| Mosquitto MQTT Broker | 提供消息订阅服务 |
| Python/Java 后端 | 订阅 MQTT 数据并进行业务处理 |

## 四、网络配置

### 4.1 PC WLAN

| 参数 | 值 |
|------|------|
| IPv4 | 192.168.3.219 |
| 网关 | 192.168.3.1 |
| 子网掩码 | 255.255.255.0 |

### 4.2 HUB

| 参数 | 值 |
|------|------|
| IPv4 | 192.168.137.1 |
| 子网掩码 | 255.255.255.0 |

### 4.3 E870 (T113 服务器)

| 参数 | 值 |
|------|------|
| 接口 | eth0 |
| IP | 192.168.137.118 |
| 子网掩码 | 255.255.255.0 |
| 网关 | 192.168.137.1 |
| DNS | 8.8.8.8 |

配置文件路径：`/etc/systemd/network/01-eth0.network`

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
|------|------|------|
| chirpstack | 8080 (REST API) / 8090 | LoRaWAN 网络服务器 |
| chirpstack-gateway-bridge | 1700 UDP | 网关桥接（UDP） |
| mosquitto | 1883 | MQTT Broker |
| postgresql | 5432 | 数据库 |
| redis | 6379 | 缓存 |

## 六、Gateway Bridge MQTT 配置

配置文件路径：`/etc/chirpstack-gateway-bridge/chirpstack-gateway-bridge.toml`

```toml
[integration.mqtt.auth.generic]
servers=["tcp://mosquitto:1883"]
username=""
password=""
```

## 七、Gateway 接入验证

### 7.1 Web 界面查看

ChirpStack → Gateway → Online

### 7.2 日志查看命令

```bash
docker logs chirpstack-chirpstack-gateway-bridge-1
```

输出：`gateway connected`

## 八、节点入网验证

节点成功 Join 后，MQTT 出现上行数据 Topic：

```text
application/{applicationID}/device/{devEUI}/event/up
```

实际示例：

```text
application/3ed92fba-9e06-4b8e-ad41-54927a0fa89d/device/0000000000000925/event/up
```

## 九、MQTT 配置

### 9.1 Broker 信息

| 参数 | 值 |
|------|------|
| 协议 | MQTT |
| 地址 | 192.168.137.118 |
| 端口 | 1883 |
| 用户名 | 无 |
| 密码 | 无 |

### 9.2 Topic 说明

| Topic | 说明 |
|-------|------|
| cn470_0/gateway/{gatewayId}/state/conn | 网关连接状态 |
| cn470_0/gateway/{gatewayId}/event/stats | 网关统计信息 |
| application/+/device/+/event/up | 节点上行数据（通配订阅） |

### 9.3 Topic 字段含义

| 字段 | 含义 |
|------|------|
| application | ChirpStack 应用 ID |
| device | 设备 DevEUI |
| event/up | 上行数据事件 |

## 十、MQTT 数据格式

ChirpStack 发送 JSON 数据，其中 data 字段为 Base64 编码后的 LoRa 应用层 Payload。

示例数据

```json
{
  "time": "2026-07-14T06:41:07.200699727+00:00",
  "deviceInfo": {
    "devEui": "0000000000000925"
  },
  "devAddr": "01f45da6",
  "rxInfo": [
    {
      "gatewayId": "0000000000000923",
      "rssi": -24,
      "snr": 14
    }
  ],
  "data": "AEGcSB0jAD7kbQABCQIrAQ=="
}
```

## 十一、Payload 解析协议

### 11.1 数据长度

16 Bytes

### 11.2 字段定义

| Byte | 字段 | 类型 | 说明 |
|------|------|------|------|
| 0-1 | seq (packetSeq) | uint16 | 数据序号 |
| 2-5 | boot_id (bootId) | uint32 | 启动编号 |
| 6-9 | sendtimems (sendTimeMs) | uint32 | 运行时间 (ms) |
| 10 | retry_count (retryCount) | uint8 | LoRaWAN 应用重传次数 |
| 11-12 | temperature | int16 | 温度 × 10 |
| 13-14 | humidity | uint16 | 湿度 × 10 |
| 15 | flags | uint8 | 状态标志 |

### 11.3 flags 位定义

| Bit | 名称 | 说明 |
|-----|------|------|
| bit0 | joined | 是否成功入网 |
| bit3 | application retry | 应用层重传 |

### 11.4 解析公式

```text
(1) 温度： temperature / 10 ℃
(2) 湿度： humidity / 10 %
```

## 十二、Payload 解析示例

### 12.1 原始 Base64

```text
AEGcSB0jAD7kbQABCQIrAQ==
```

### 12.2 解码 HEX

```text
00 41 9c 48 1d 23 00 3e e4 6d 00 01 09 02 2b 01
```

### 12.3 解析结果

| 字段 | 原始值 (HEX) | 解析结果 |
|------|--------------|----------|
| seq | 0x0041 | 65 |
| boot_id | 0x9c481d23 | 2621447459 |
| sendtimems | 0x003ee46d | 4121709 |
| retry_count | 0x00 | 0 |
| temperature | 0x0109 | 265 → 26.5 ℃ |
| humidity | 0x022b | 555 → 55.5 % |
| flags | 0x01 | joined = True |

## 十三、MQTT 接收与解析流程

```text
MQTT Subscribe (JSON)
      |
      ↓
读取 data 字段
      |
      ↓
Base64 解码
      |
      ↓
得到16字节 payload
      |
      ↓
按协议解析温湿度
      |
      ↓
数据库存储或可视化
```

图2 MQTT 接收与解析流程

## 十四、MQTT 验证代码

### 14.1 文件

```text
mqtt_receiver.py
```

### 14.2 功能

1. MQTT 订阅
2. Base64 解码
3. Payload 解析
4. 温湿度输出

### 14.3 输出示例

```text
正在连接MQTT...
MQTT连接成功
订阅: application/+/device/+/event/up

========================
Topic:
application/3ed92fba-9e06-4b8e-ad41-54927a0fa89d/device/0000000000000925/event/up

设备:
DevEUI: 0000000000000925
Name: Ebyte Test Device 470

时间:
2026-07-14T07:06:58.216724017+00:00

无线参数:
Gateway: 0000000000000923
RSSI: -17
SNR: 14.0

Base64:
AFqcSB0jAFaO4wABBAImAQ==

HEX:
005a9c481d2300568ee3000104022601

=======解析结果=======
温度: 26.0 ℃
湿度: 55.0 %
序号: 90
Boot ID: 0x9c481d23
LoRaWAN重传: 0
已入网: True
应用层重传: False
=====================
```
