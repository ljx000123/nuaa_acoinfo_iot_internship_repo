# 03 物联网 ZigBee 应用案例开发

本目录用于管理 ZigBee 方向实验代码、文档、PPT 和测试记录。

## 建议实验

| 编号 | 实验名称 | 交付物 |
| --- | --- | --- |
| Z1 | CC2530 开发环境、烧录与串口 Hello 实验 | 代码 + 指导书 + PPT |
| Z2 | ZigBee 协调器/路由器/终端组网实验 | 代码 + 指导书 + PPT |
| Z3 | ZigBee 传感数据采集与 MQTT 发布实验 | 代码 + 指导书 + PPT |
| Z4 | ZigBee 下行控制与智能开关实验 | 代码 + 指导书 + PPT |
| Z5 | ZigBee-RS485 无线透传与工业数据采集实验 | 代码 + 指导书 + PPT |
| Z7 | 智能家居环境监测与联动告警实验 | 代码 + 指导书 + PPT |
| Z8 | ZigBee 工业现场数据采集综合实验 | 代码 + 指导书 + PPT |

说明：Z6 属于协议桥接组，目录放在 `01_protocol_bridge/experiments/`。

## 目录建议

```text
03_zigbee/
  assets/
  config/
  docs/
  examples/
  experiments/
    Z01_cc2530_hello/
    Z02_networking/
    Z03_sensor_to_mqtt/
    Z04_downlink_control/
    Z05_rs485_transparent/
    Z07_smart_home_alarm/
    Z08_industrial_collection/
  scripts/
  src/
  tests/
```

每个实验目录下均包含 `src/`、`config/`、`docs/`、`slides/`、`tests/`、`assets/` 六个子目录。
