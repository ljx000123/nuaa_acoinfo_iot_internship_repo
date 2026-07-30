#!/usr/bin/env python3

import json
import base64
import paho.mqtt.client as mqtt


# ==================================================
# MQTT配置
# ==================================================

MQTT_HOST = "192.168.200.221"
MQTT_PORT = 1883



# ==================================================
# MQTT Topic
# ==================================================

MQTT_TOPICS = [

    # S3 LoRaWAN经过转换程序后的Topic
    (
        "bridge/uplink/lora/0000000000000925/data",
        1
    ),


    # S3 WiFi直连MQTT
    (
        "bridge/uplink/generic/eora_s3_400tb_001/data",
        1
    )

]



# ==================================================
# S3 LoRaWAN Payload解析
# 43 Bytes
# ==================================================

def parse_s3_lora(payload):


    if len(payload) != 43:

        return None



    return {


        # Byte 0-1
        "seq":
            int.from_bytes(
                payload[0:2],
                "big"
            ),



        # Byte 2-5
        "boot_id":
            int.from_bytes(
                payload[2:6],
                "big"
            ),



        # Byte 6-9
        "send_time_ms":
            int.from_bytes(
                payload[6:10],
                "big"
            ),



        # Byte 10
        "lorawan_retry_count":
            payload[10],



        # Byte 11-12
        "temperature":
            int.from_bytes(
                payload[11:13],
                "big",
                signed=True
            ) / 10,



        # Byte 13-14
        "humidity":
            int.from_bytes(
                payload[13:15],
                "big"
            ) / 10,



        # Byte 15
        "flags":
            payload[15],



        # Byte 16-17
        "soil_moisture":
            int.from_bytes(
                payload[16:18],
                "big"
            ) / 10,



        # Byte 18-19
        "soil_raw":
            int.from_bytes(
                payload[18:20],
                "big"
            ),



        # Byte 20-21
        "rain_level":
            int.from_bytes(
                payload[20:22],
                "big"
            ) / 10,



        # Byte 22-23
        "rain_raw":
            int.from_bytes(
                payload[22:24],
                "big"
            ),



        # Byte 24
        "motor_running":
            bool(
                payload[24]
            ),



        # Byte 25
        "servo_angle":
            payload[25],



        # Byte 26
        "led_status":
            "on"
            if payload[26]
            else
            "off",



        # Byte 27
        "signal":
            int.from_bytes(
                payload[27:28],
                "big",
                signed=True
            ),



        # Byte37-38
        "command_counter":
            int.from_bytes(
                payload[37:39],
                "big"
            ),



        # Byte39
        "command_source":
            payload[39],



        # Byte40
        "command_target":
            payload[40],



        # Byte41
        "command_value":
            payload[41],



        # Byte42
        "command_result":
            payload[42]

    }



# ==================================================
# S3 WiFi JSON解析
# ==================================================

def parse_wifi(data):


    print(
        "\n========== S3 WiFi =========="
    )


    print(
        "Device:",
        data.get("device_id")
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
        "Soil:",
        data.get("soil_moisture"),
        "%"
    )


    print(
        "Rain:",
        data.get("rain_level"),
        "%"
    )


    print(
        "Motor:",
        "running"
        if data.get("motor_running")
        else
        "stopped"
    )


    print(
        "Servo:",
        data.get("servo_angle")
    )


    print(
        "LED:",
        data.get("led_status")
    )


    print(
        "Signal:",
        data.get("signal"),
        "dBm"
    )


    print(
        "============================"
    )



# ==================================================
# S3 LoRaWAN解析
# ==================================================

def parse_lora(data, topic):


    device_id = topic.split("/")[3]


    print(
        "\nDevice:",
        device_id
    )



    payload_b64 = data.get(
        "data"
    )


    if not payload_b64:


        print(
            "无Payload"
        )


        return



    try:

        payload = base64.b64decode(
            payload_b64
        )


    except Exception as e:


        print(
            "Base64解析失败:",
            e
        )


        return




    print(
        "Payload Length:",
        len(payload)
    )


    print(
        "HEX:",
        payload.hex()
    )



    s3 = parse_s3_lora(
        payload
    )



    if s3 is None:


        print(
            "未知S3 Payload"
        )


        return




    print(
        "\n======= S3 LoRaWAN ======="
    )



    print(
        "Seq:",
        s3["seq"]
    )


    print(
        "Boot ID:",
        s3["boot_id"]
    )


    print(
        "Send Time:",
        s3["send_time_ms"]
    )


    print(
        "Temperature:",
        s3["temperature"],
        "℃"
    )


    print(
        "Humidity:",
        s3["humidity"],
        "%"
    )


    print(
        "Soil:",
        s3["soil_moisture"],
        "%"
    )


    print(
        "Rain:",
        s3["rain_level"],
        "%"
    )



    print(
        "Motor:",
        "running"
        if s3["motor_running"]
        else
        "stopped"
    )


    print(
        "Servo:",
        s3["servo_angle"]
    )


    print(
        "LED:",
        s3["led_status"]
    )


    print(
        "Signal:",
        s3["signal"],
        "dBm"
    )


    print(
        "LoRa Retry:",
        s3["lorawan_retry_count"]
    )


    print(
        "Command Counter:",
        s3["command_counter"]
    )


    print(
        "Command:",
        "source=",
        s3["command_source"],
        "target=",
        s3["command_target"],
        "value=",
        s3["command_value"],
        "result=",
        s3["command_result"]
    )


    print(
        "=========================="
    )




# ==================================================
# MQTT回调
# ==================================================

def on_connect(client, userdata, flags, rc):


    if rc == 0:


        print(
            "MQTT连接成功"
        )


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




def on_message(client, userdata, msg):


    print(
        "\n============================"
    )


    print(
        "Topic:",
        msg.topic
    )



    try:


        data = json.loads(
            msg.payload.decode()
        )


    except Exception as e:


        print(
            "JSON解析错误:",
            e
        )


        return




    # WiFi S3

    if msg.topic.startswith(
        "bridge/uplink/generic/"
    ):


        parse_wifi(
            data
        )



    # LoRaWAN S3

    elif msg.topic.startswith(
        "bridge/uplink/lora/"
    ):


        parse_lora(
            data,
            msg.topic
        )




# ==================================================
# Main
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