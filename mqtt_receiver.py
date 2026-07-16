import json
import base64
import paho.mqtt.client as mqtt


# ==================================================
# MQTT配置
# ==================================================

MQTT_HOST = "192.168.3.219"

MQTT_PORT = 1883


# ==================================================
# 统一MQTT Topic
# ==================================================

MQTT_TOPICS = [

    # LoRa统一topic
    (
        "bridge/uplink/lora/+/data",
        1
    ),

    # S3 WiFi统一topic
    (
        "bridge/uplink/generic/eora_s3_400tb_001/data",
        1
    )

]


# ==================================================
# LoRa Payload解析
# ==================================================

def parse_payload(payload):

    if len(payload) != 16:

        print(
            "Payload长度异常:",
            len(payload)
        )

        return None


    seq = int.from_bytes(
        payload[0:2],
        byteorder="big"
    )


    boot_id = int.from_bytes(
        payload[2:6],
        byteorder="big"
    )


    send_time_ms = int.from_bytes(
        payload[6:10],
        byteorder="big"
    )


    retry_count = payload[10]


    temp_raw = int.from_bytes(
        payload[11:13],
        byteorder="big",
        signed=True
    )


    temperature = temp_raw / 10.0



    humi_raw = int.from_bytes(
        payload[13:15],
        byteorder="big"
    )


    humidity = humi_raw / 10.0



    flags = payload[15]


    return {

        "seq": seq,

        "boot_id": hex(boot_id),

        "send_time_ms": send_time_ms,

        "lorawan_retry_count": retry_count,

        "temperature": temperature,

        "humidity": humidity,

        "joined": bool(flags & 0x01),

        "application_retry": bool(flags & 0x08),

        "flags": hex(flags)

    }



# ==================================================
# MQTT连接
# ==================================================

def on_connect(client, userdata, flags, rc):

    if rc == 0:

        print("MQTT连接成功")


        client.subscribe(
            MQTT_TOPICS
        )


        print(
            "订阅Topic:"
        )


        for topic, qos in MQTT_TOPICS:

            print(
                " ",
                topic
            )


    else:

        print(
            "MQTT连接失败:",
            rc
        )



# ==================================================
# MQTT消息处理
# ==================================================

def on_message(client, userdata, msg):


    print("\n========================")

    print(
        "Topic:"
    )

    print(
        msg.topic
    )



    try:

        data = json.loads(
            msg.payload.decode()
        )


    except Exception as e:

        print(
            "JSON解析失败:",
            e
        )

        return



    # ==================================================
    # S3 WiFi 数据
    # ==================================================

    if msg.topic == \
        "bridge/uplink/generic/eora_s3_400tb_001/data":


        print(
            "\n========== WiFi S3数据 =========="
        )


        print(
            "Device ID:",
            data.get("device_id")
        )


        print(
            "Name:",
            data.get("name")
        )


        print(
            "Type:",
            data.get("type")
        )


        print(
            "Status:",
            data.get("status")
        )


        print(
            "Source:",
            data.get("source")
        )


        print(
            "Timestamp:",
            data.get("timestamp")
        )


        print(
            "Temperature:",
            data.get("temperature"),
            "℃"
        )


        print(
            "Humidity:",
            data.get("humidity"),
            "%"
        )


        print(
            "Signal:",
            data.get("signal")
        )



        raw = data.get(
            "raw",
            {}
        )


        print(
            "\nRaw:"
        )


        print(
            "DevEUI:",
            raw.get("dev_eui")
        )


        print(
            "Boot ID:",
            raw.get("boot_id")
        )


        print(
            "Seq:",
            raw.get("seq")
        )


        print(
            "WiFi Retry:",
            raw.get("wifi_retry_count")
        )


        print(
            "Link:",
            raw.get("link")
        )


        print(
            "============================"
        )


        return



    # ==================================================
    # LoRa 数据
    # ==================================================

    if msg.topic.startswith(
        "bridge/uplink/lora/"
    ):


        print(
            "\n========== LoRaWAN数据 =========="
        )


        # topic:
        # bridge/uplink/lora/{device_id}/data

        parts = msg.topic.split("/")


        if len(parts) >= 5:

            device_id = parts[3]

        else:

            device_id = "unknown"



        print(
            "Device ID:",
            device_id
        )


        device_info = data.get(
            "deviceInfo",
            {}
        )


        print(
            "DevEUI:",
            device_info.get(
                "devEui"
            )
        )


        print(
            "设备:",
            device_info.get(
                "deviceName"
            )
        )



        print(
            "时间:",
            data.get("time")
        )



        rx_info = data.get(
            "rxInfo",
            []
        )


        if rx_info:


            rx = rx_info[0]


            print(
                "Gateway:",
                rx.get("gatewayId")
            )


            print(
                "RSSI:",
                rx.get("rssi")
            )


            print(
                "SNR:",
                rx.get("snr")
            )



        payload_b64 = data.get(
            "data"
        )


        if payload_b64 is None:

            print(
                "无Payload"
            )

            return



        print(
            "Base64:",
            payload_b64
        )


        payload = base64.b64decode(
            payload_b64
        )


        print(
            "HEX:",
            payload.hex()
        )



        result = parse_payload(
            payload
        )



        if result:


            print(
                "\n======= LoRa解析结果 ======="
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
                "LoRa重传:",
                result["lorawan_retry_count"]
            )


            print(
                "Joined:",
                result["joined"]
            )


            print(
                "App Retry:",
                result["application_retry"]
            )


            print(
                "============================"
            )



# ==================================================
# 主程序
# ==================================================

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION1
)


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