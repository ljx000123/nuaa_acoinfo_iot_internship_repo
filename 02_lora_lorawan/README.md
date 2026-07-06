# 02 物联网 LoRa/LoRaWAN 应用案例开发

本目录用于管理 LoRa/LoRaWAN 方向实验代码、文档、PPT 和测试记录。

## 建议实验

| 编号 | 实验名称 | 交付物 |
| --- | --- | --- |
| L1 | LoRa 开发环境与点对点 Hello 实验 | 代码 + 指导书 + PPT |
| L2 | LoRa 传感数据采集与上报实验 | 代码 + 指导书 + PPT |
| L3 | LoRa 可靠传输：ACK、重传与丢包统计 | 代码 + 指导书 + PPT |
| L4 | LoRaWAN 网关接入与 MQTT 上行 | 代码 + 指导书 + PPT |
| L5 | LoRa MQTT -> VSOA 上行协议转换实验 | 代码 + 指导书 + PPT |
| L6 | LoRa VSOA -> MQTT 下行控制实验 | 代码 + 指导书 + PPT |
| L7 | LoRa 链路质量监测与可视化实验 | 代码 + 指导书 + PPT |
| L8 | LoRa 低功耗环境监测综合场景 | 代码 + 指导书 + PPT |

## 目录建议

```text
02_lora_lorawan/
  assets/
  config/
  docs/
  examples/
  experiments/
    L01_lora_hello/
    L02_sensor_uplink/
    L03_ack_retransmit/
    L04_lorawan_mqtt/
    L05_mqtt_to_vsoa/
    L06_vsoa_to_mqtt/
    L07_link_quality/
    L08_low_power_monitoring/
  scripts/
  src/
  tests/
```

每个实验目录下均包含 `src/`、`config/`、`docs/`、`slides/`、`tests/`、`assets/` 六个子目录。
