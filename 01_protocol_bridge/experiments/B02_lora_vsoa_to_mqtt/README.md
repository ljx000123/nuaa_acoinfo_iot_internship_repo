# LoRa VSOA -> MQTT 下行桥接支撑

## 任务定位

支撑 L6，将 VSOA 控制命令转换为 LoRa/LoRaWAN 下行 topic 和 payload。

## 关联实验

L6、L8

## 目录结构

```text
B02_lora_vsoa_to_mqtt/
  src/      桥接或测试相关代码
  config/   topic、schema、服务地址等配置
  docs/     接口说明、测试说明、联调记录
  slides/   汇报材料
  tests/    自动化测试、验收用例
  assets/   日志截图、链路图、测试截图
```

## 交付检查

- [ ] 配置文件可复用
- [ ] 测试脚本可运行
- [ ] 日志格式统一
- [ ] 能支撑相关实验复现
- [ ] 问题清单和验收记录已更新
