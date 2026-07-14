import json
import base64
import paho.mqtt.client as mqtt
from datetime import datetime


# ==========================
# MQTT配置
# ==========================

MQTT_HOST = "192.168.137.118"
# 如果后端和ChirpStack同机器可以localhost
# 如果其他电脑连接，需要填写T113的IP

MQTT_PORT = 1883

MQTT_TOPIC = "application/+/device/+/event/up"


# ==========================
# Payload解析
# ==========================

def parse_payload(payload):

    if len(payload) != 16:
        print("Payload长度异常:",
              len(payload))
        return None


    # Byte 0-1
    seq = int.from_bytes(
        payload[0:2],
        byteorder="big"
    )


    # Byte 2-5
    boot_id = int.from_bytes(
        payload[2:6],
        byteorder="big"
    )


    # Byte 6-9
    send_time_ms = int.from_bytes(
        payload[6:10],
        byteorder="big"
    )


    # Byte 10
    retry_count = payload[10]


    # Byte 11-12
    temp_raw = int.from_bytes(
        payload[11:13],
        byteorder="big",
        signed=True
    )

    temperature = temp_raw / 10.0


    # Byte 13-14
    humi_raw = int.from_bytes(
        payload[13:15],
        byteorder="big"
    )

    humidity = humi_raw / 10.0


    # Byte15
    flags = payload[15]


    joined = bool(
        flags & 0x01
    )

    app_retry = bool(
        flags & 0x08
    )


    return {

        "seq": seq,

        "boot_id":
            hex(boot_id),

        "send_time_ms":
            send_time_ms,

        "lorawan_retry_count":
            retry_count,

        "temperature":
            temperature,

        "humidity":
            humidity,

        "joined":
            joined,

        "application_retry":
            app_retry,

        "flags":
            hex(flags)
    }



# ==========================
# MQTT连接回调
# ==========================

def on_connect(client, userdata,
                flags, rc):

    if rc == 0:

        print(
            "MQTT连接成功"
        )

        client.subscribe(
            MQTT_TOPIC
        )

        print(
            "订阅:",
            MQTT_TOPIC
        )

    else:

        print(
            "MQTT连接失败:",
            rc
        )



# ==========================
# MQTT消息回调
# ==========================

def on_message(client,
                userdata,
                msg):


    print("\n========================")

    print(
        "Topic:"
    )

    print(
        msg.topic
    )


    # MQTT JSON
    data = json.loads(
        msg.payload.decode()
    )


    # ======================
    # 基础信息
    # ======================

    device_info = (
        data["deviceInfo"]
    )


    print("\n设备:")

    print(
        "DevEUI:",
        device_info["devEui"]
    )


    print(
        "Name:",
        device_info["deviceName"]
    )


    print("\n时间:")

    print(
        data["time"]
    )


    # ======================
    # 网关信息
    # ======================

    rx = data["rxInfo"][0]


    print("\n无线参数:")

    print(
        "Gateway:",
        rx["gatewayId"]
    )


    print(
        "RSSI:",
        rx["rssi"]
    )


    print(
        "SNR:",
        rx["snr"]
    )


    # ======================
    # Payload
    # ======================


    payload_b64 = data["data"]


    print("\nBase64:")

    print(
        payload_b64
    )


    payload = base64.b64decode(
        payload_b64
    )


    print("\nHEX:")

    print(
        payload.hex()
    )


    result = parse_payload(
        payload
    )


    if result:


        print(
            "\n=======解析结果======="
        )


        print(
            "温度:",
            result["temperature"],
            "℃"
        )


        print(
            "湿度:",
            result["humidity"],
            "%"
        )


        print(
            "序号:",
            result["seq"]
        )


        print(
            "Boot ID:",
            result["boot_id"]
        )


        print(
            "LoRaWAN重传:",
            result["lorawan_retry_count"]
        )


        print(
            "已入网:",
            result["joined"]
        )


        print(
            "应用层重传:",
            result["application_retry"]
        )


        print(
            "====================="
        )



# ==========================
# 主程序
# ==========================

client = mqtt.Client()


client.on_connect = on_connect

client.on_message = on_message


print(
    "正在连接MQTT..."
)


client.connect(
    MQTT_HOST,
    MQTT_PORT,
    60
)


client.loop_forever()