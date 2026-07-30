/**************************************************************************************************
  Filename:       zcl_samplesw.c
  Revised:        $Date: 2015-08-19 17:11:00 -0700 (Wed, 19 Aug 2015) $
  Revision:       $Revision: 44460 $

  Description:    Zigbee Cluster Library - sample switch application.


  Copyright 2006-2013 Texas Instruments Incorporated. All rights reserved.

  IMPORTANT: Your use of this Software is limited to those specific rights
  granted under the terms of a software license agreement between the user
  who downloaded the software, his/her employer (which must be your employer)
  and Texas Instruments Incorporated (the "License").  You may not use this
  Software unless you agree to abide by the terms of the License. The License
  limits your use, and you acknowledge, that the Software may not be modified,
  copied or distributed unless embedded on a Texas Instruments microcontroller
  or used solely and exclusively in conjunction with a Texas Instruments radio
  frequency transceiver, which is integrated into your product.  Other than for
  the foregoing purpose, you may not use, reproduce, copy, prepare derivative
  works of, modify, distribute, perform, display or sell this Software and/or
  its documentation for any purpose.

  YOU FURTHER ACKNOWLEDGE AND AGREE THAT THE SOFTWARE AND DOCUMENTATION ARE
  PROVIDED �AS IS� WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESS OR IMPLIED,
  INCLUDING WITHOUT LIMITATION, ANY WARRANTY OF MERCHANTABILITY, TITLE,
  NON-INFRINGEMENT AND FITNESS FOR A PARTICULAR PURPOSE. IN NO EVENT SHALL
  TEXAS INSTRUMENTS OR ITS LICENSORS BE LIABLE OR OBLIGATED UNDER CONTRACT,
  NEGLIGENCE, STRICT LIABILITY, CONTRIBUTION, BREACH OF WARRANTY, OR OTHER
  LEGAL EQUITABLE THEORY ANY DIRECT OR INDIRECT DAMAGES OR EXPENSES
  INCLUDING BUT NOT LIMITED TO ANY INCIDENTAL, SPECIAL, INDIRECT, PUNITIVE
  OR CONSEQUENTIAL DAMAGES, LOST PROFITS OR LOST DATA, COST OF PROCUREMENT
  OF SUBSTITUTE GOODS, TECHNOLOGY, SERVICES, OR ANY CLAIMS BY THIRD PARTIES
  (INCLUDING BUT NOT LIMITED TO ANY DEFENSE THEREOF), OR OTHER SIMILAR COSTS.

  Should you have any questions regarding your right to use this Software,
  contact Texas Instruments Incorporated at www.TI.com.
**************************************************************************************************/

/*********************************************************************
  This application implements a ZigBee On/Off Switch, based on Z-Stack 3.0.

  This application is based on the common sample-application user interface. Please see the main
  comment in zcl_sampleapp_ui.c. The rest of this comment describes only the content specific for
  this sample applicetion.
  
  Application-specific UI peripherals being used:

  - none (LED1 is currently unused by this application).

  Application-specific menu system:

    <TOGGLE LIGHT> Send an On, Off or Toggle command targeting appropriate devices from the binding table.
      Pressing / releasing [OK] will have the following functionality, depending on the value of the 
      zclSampleSw_OnOffSwitchActions attribute:
      - OnOffSwitchActions == 0: pressing [OK] will send ON command, releasing it will send OFF command;
      - OnOffSwitchActions == 1: pressing [OK] will send OFF command, releasing it will send ON command;
      - OnOffSwitchActions == 2: pressing [OK] will send TOGGLE command, releasing it will not send any command.

*********************************************************************/

#if ! defined ZCL_ON_OFF
#error ZCL_ON_OFF must be defined for this project.
#endif

/*********************************************************************
 * INCLUDES
 */
#include "ZComDef.h"
#include "OSAL.h"
#include "AF.h"
#include "ZDApp.h"
#include "ZDObject.h"
#include "ZDProfile.h"
#include "MT_SYS.h"

#include "zcl.h"
#include "zcl_general.h"
#include "zcl_ha.h"
#include "zcl_samplesw.h"
#include "zcl_diagnostic.h"

#include "onboard.h"

/* HAL */
#include "hal_lcd.h"
#include "hal_led.h"
#include "hal_key.h"
#include "hal_adc.h"
#include "hal_delay.h"
#include "cc2530_ioctl.h"

#if defined (OTA_CLIENT) && (OTA_CLIENT == TRUE)
#include "zcl_ota.h"
#include "hal_ota.h"
#endif

#include "bdb.h"
#include "bdb_interface.h"
#include "ZComDef.h"
#include "ZDSecMgr.h"


#include <stdio.h>

/*********************************************************************
 * MACROS
 */

#define APP_TITLE "TI Sample Switch"
#define EBYTE_TRANSPARENT_CLUSTER_ID  0xFC08

#define SENSOR_ADC_REF_MV       3300UL
#define SENSOR_ADC_POSITIVE_FS  2047UL

typedef struct
{
  uint8 ok;
  uint8 temperature;
  uint8 humidity;
} envDht11Data_t;

static void envDht11SetIdle(void);
static uint8 envDht11ReadByte(void);
static envDht11Data_t envDht11Read(void);

/*********************************************************************
 * TYPEDEFS
 */

/*********************************************************************
 * GLOBAL VARIABLES
 */
byte zclSampleSw_TaskID;

uint8 zclSampleSwSeqNum;

uint8 zclSampleSw_OnOffSwitchType = ON_OFF_SWITCH_TYPE_MOMENTARY;

uint8 zclSampleSw_OnOffSwitchActions;

/*********************************************************************
 * GLOBAL FUNCTIONS
 */

/*********************************************************************
 * LOCAL VARIABLES
 */
afAddrType_t zclSampleSw_DstAddr;

// Endpoint to allow SYS_APP_MSGs
static endPointDesc_t sampleSw_TestEp =
{
  SAMPLESW_ENDPOINT,                  // endpoint
  0,
  &zclSampleSw_TaskID,
  (SimpleDescriptionFormat_t *)NULL,  // No Simple description for this test endpoint
  (afNetworkLatencyReq_t)0            // No Network Latency req
};

// 在文件顶部添加
static cId_t ebikePort01OutClusters[] =
{
  EBYTE_TRANSPARENT_CLUSTER_ID
};

static cId_t ebikePort01InClusters[] =
{
  EBYTE_TRANSPARENT_CLUSTER_ID,
  ZCL_CLUSTER_ID_GEN_ON_OFF,
  ZCL_CLUSTER_ID_GEN_LEVEL_CONTROL
};

static SimpleDescriptionFormat_t ebikePort01SimpleDesc =
{
  0x01,                                  // endpoint
  ZCL_HA_PROFILE_ID,                     // Home Automation profile (0x0104)
  ZCL_HA_DEVICEID_ON_OFF_LIGHT_SWITCH,   // device ID already used by this sample
  0,                                     // device version
  0,                                     // reserved
  3,                                     // number of input clusters
  ebikePort01InClusters,                 // FC08, On/Off and Level Control
  1,                                     // number of output clusters
  ebikePort01OutClusters                 // output cluster 0xFC08
};

static endPointDesc_t ebikePort01Ep =
{
  0x01,
  0,
  &zclSampleSw_TaskID,
  &ebikePort01SimpleDesc,
  (afNetworkLatencyReq_t)0
};
 
//static uint8 aProcessCmd[] = { 1, 0, 0, 0 }; // used for reset command, { length + cmd0 + cmd1 + data }

devStates_t zclSampleSw_NwkState = DEV_INIT;

#if defined (OTA_CLIENT) && (OTA_CLIENT == TRUE)
#define DEVICE_POLL_RATE                 8000   // Poll rate for end device
#endif

#define SAMPLESW_TOGGLE_TEST_EVT   0x1000
#define SAMPLESW_FACTORY_RESET_EVT 0x000A
#define SENSOR_REPORT_EVT       0x2000
#define SENSOR_SAMPLE_PERIOD    1000
static uint8 bandwidthStage = 0;
static uint16 bandwidthPeriodMs = SENSOR_SAMPLE_PERIOD;

// Stability settings for the mains-powered end device.
#undef SAMPLEAPP_REJOIN_PERIOD
#define SAMPLEAPP_REJOIN_PERIOD 5000
#undef SAMPLEAPP_END_DEVICE_REJOIN_DELAY
#define SAMPLEAPP_END_DEVICE_REJOIN_DELAY 30000
/*********************************************************************
 * LOCAL FUNCTIONS
 */
static void zclSampleSw_HandleKeys( byte shift, byte keys );
static uint16 zclSampleSw_BandwidthPeriodForStage(uint8 stage);
static void zclSampleSw_BasicResetCB( void );

static void zclSampleSw_ProcessCommissioningStatus(bdbCommissioningModeMsg_t *bdbCommissioningModeMsg);


// Functions to process ZCL Foundation incoming Command/Response messages
static void zclSampleSw_ProcessIncomingMsg( zclIncomingMsg_t *msg );
#ifdef ZCL_READ
static uint8 zclSampleSw_ProcessInReadRspCmd( zclIncomingMsg_t *pInMsg );
#endif
#ifdef ZCL_WRITE
static uint8 zclSampleSw_ProcessInWriteRspCmd( zclIncomingMsg_t *pInMsg );
#endif
static uint8 zclSampleSw_ProcessInDefaultRspCmd( zclIncomingMsg_t *pInMsg );
#ifdef ZCL_DISCOVER
static uint8 zclSampleSw_ProcessInDiscCmdsRspCmd( zclIncomingMsg_t *pInMsg );
static uint8 zclSampleSw_ProcessInDiscAttrsRspCmd( zclIncomingMsg_t *pInMsg );
static uint8 zclSampleSw_ProcessInDiscAttrsExtRspCmd( zclIncomingMsg_t *pInMsg );
#endif

#if defined (OTA_CLIENT) && (OTA_CLIENT == TRUE)
static void zclSampleSw_ProcessOTAMsgs( zclOTA_CallbackMsg_t* pMsg );
#endif

#define ZCLSAMPLESW_UART_BUF_LEN        128
static uint8 zclSampleSw_UartBuf[ZCLSAMPLESW_UART_BUF_LEN];
static void zclSampleSw_InitUart(void);
static void zclSampleSw_UartCB(uint8 port, uint8 event);
static void zclSampleSw_ProcessDownlink(afIncomingMSGPacket_t *pkt);

static uint8 zclSampleSw_ActuatorState = 0;
static uint8 zclSampleSw_AfTransId = 0;
static uint8 zclSampleSw_AckSequence = 0;

static void zclSampleSw_SendControlAck(uint8 action, uint16 clusterId)
{
  uint8 ackData[10];
  afAddrType_t destAddr;

  if (devState != DEV_END_DEVICE)
    return;

  ackData[0] = 0x15;
  ackData[1] = 0x00;
  ackData[2] = 0x20;
  ackData[3] = zclSampleSw_AckSequence++;
  ackData[4] = 0x00;
  ackData[5] = 0xA1;
  ackData[6] = action;
  ackData[7] = zclSampleSw_ActuatorState;
  ackData[8] = LO_UINT16(clusterId);
  ackData[9] = HI_UINT16(clusterId);

  destAddr.addrMode = (afAddrMode_t)Addr16Bit;
  destAddr.endPoint = 0x01;
  destAddr.addr.shortAddr = 0x0000;

  AF_DataRequest(&destAddr,
                 &ebikePort01Ep,
                 EBYTE_TRANSPARENT_CLUSTER_ID,
                 sizeof(ackData),
                 ackData,
                 &zclSampleSw_AfTransId,
                 AF_DISCV_ROUTE,
                 AF_DEFAULT_RADIUS);
}

static void zclSampleSw_SetActuator(uint8 action)
{
  if (action == 0)
    zclSampleSw_ActuatorState = 0;
  else if (action == 1)
    zclSampleSw_ActuatorState = 1;
  else if (action == 2)
    zclSampleSw_ActuatorState ^= 1;
  else
    return;

  // Three-wire active-low buzzer module: IO is connected to P0.2.
  P0_2 = zclSampleSw_ActuatorState ? 0 : 1;
  P0_4 = zclSampleSw_ActuatorState;
}

static void zclSampleSw_ProcessDownlink(afIncomingMSGPacket_t *pkt)
{
  uint8 command;
  uint8 parameterOffset;

  if ((pkt == NULL) || (pkt->cmd.Data == NULL) || (pkt->cmd.DataLength < 3))
    return;

  command = pkt->cmd.Data[2];
  parameterOffset = 3;

  if ((pkt->clusterId == EBYTE_TRANSPARENT_CLUSTER_ID) &&
      (pkt->cmd.Data[0] & 0x04))
  {
    if (pkt->cmd.DataLength < 5)
      return;
    command = pkt->cmd.Data[4];
    parameterOffset = 5;
  }

  if (pkt->clusterId == ZCL_CLUSTER_ID_GEN_ON_OFF)
  {
    zclSampleSw_SetActuator(command);
    if (command <= 2)
      zclSampleSw_SendControlAck(command, pkt->clusterId);
  }
  else if ((pkt->clusterId == ZCL_CLUSTER_ID_GEN_LEVEL_CONTROL) &&
           (command == 0x00) && (pkt->cmd.DataLength > parameterOffset))
  {
    uint8 action = pkt->cmd.Data[parameterOffset] ? 1 : 0;
    zclSampleSw_SetActuator(action);
    zclSampleSw_SendControlAck(action, pkt->clusterId);
  }
  else if ((pkt->clusterId == EBYTE_TRANSPARENT_CLUSTER_ID) &&
           (command == 0x00) && (pkt->cmd.DataLength > parameterOffset))
  {
    uint8 action = pkt->cmd.Data[parameterOffset];
    zclSampleSw_SetActuator(action);
    if (action <= 2)
      zclSampleSw_SendControlAck(action, pkt->clusterId);
  }
}


/*********************************************************************
 * CONSTANTS
 */

/*********************************************************************
 * REFERENCED EXTERNALS
 */
extern int16 zdpExternalStateTaskID;

static void envDht11SetIdle(void)
{
  CC2530_IOCTL(0, 6, CC2530_OUTPUT);
  P0_6 = 1;
}

static uint8 envDht11ReadByte(void)
{
  uint8 value = 0;
  uint8 i;

  for (i = 0; i < 8; i++)
  {
    uint16 timeout = 5350;
    while (!P0_6 && timeout--);
    if (!timeout) return value;

    delayUsIn32Mhz(50);
    value <<= 1;
    if (P0_6) value |= 1;

    timeout = 1070;
    while (P0_6 && timeout--);
    if (!timeout) return value;
  }

  return value;
}

static envDht11Data_t envDht11Read(void)
{
  envDht11Data_t result;
  uint8 humiInt = 0;
  uint8 humiFrac = 0;
  uint8 tempInt = 0;
  uint8 tempFrac = 0;
  uint8 checksum = 0;
  uint16 timeout;

  result.ok = 0;
  result.temperature = 0;
  result.humidity = 0;

  CC2530_IOCTL(0, 6, CC2530_OUTPUT);
  P0_6 = 0;
  delayMs(SYSCLK_32MHZ, 30);
  P0_6 = 1;
  delayUsIn32Mhz(32);
  // Port 0 shares one pull-direction control bit.  Pull-down here would also
  // pull P0.1/S1 low and falsely trigger the factory-reset key handler.
  CC2530_IOCTL(0, 6, CC2530_INPUT_PULLUP);

  if (!P0_6)
  {
    timeout = 1070;
    while (!P0_6 && timeout--);
    if (!timeout) goto Exit;

    delayUsIn32Mhz(80);
    timeout = 1070;
    while (P0_6 && timeout--);
    if (!timeout) goto Exit;

    humiInt = envDht11ReadByte();
    humiFrac = envDht11ReadByte();
    tempInt = envDht11ReadByte();
    tempFrac = envDht11ReadByte();
    checksum = envDht11ReadByte();

    if (checksum == (uint8)(humiInt + humiFrac + tempInt + tempFrac) &&
        tempInt <= 50 && humiInt >= 20 && humiInt <= 95)
    {
      result.ok = 1;
      result.temperature = tempInt;
      result.humidity = humiInt;
    }
  }

Exit:
  envDht11SetIdle();
  return result;
}

/*********************************************************************
 * ZCL General Profile Callback table
 */
static zclGeneral_AppCallbacks_t zclSampleSw_CmdCallbacks =
{
  zclSampleSw_BasicResetCB,               // Basic Cluster Reset command
  NULL,                                   // Identify Trigger Effect command
  NULL,                                   // On/Off cluster commands
  NULL,                                   // On/Off cluster enhanced command Off with Effect
  NULL,                                   // On/Off cluster enhanced command On with Recall Global Scene
  NULL,                                   // On/Off cluster enhanced command On with Timed Off
#ifdef ZCL_LEVEL_CTRL
  NULL,                                   // Level Control Move to Level command
  NULL,                                   // Level Control Move command
  NULL,                                   // Level Control Step command
  NULL,                                   // Level Control Stop command
#endif
#ifdef ZCL_GROUPS
  NULL,                                   // Group Response commands
#endif
#ifdef ZCL_SCENES
  NULL,                                   // Scene Store Request command
  NULL,                                   // Scene Recall Request command
  NULL,                                   // Scene Response command
#endif
#ifdef ZCL_ALARMS
  NULL,                                   // Alarm (Response) commands
#endif
#ifdef SE_UK_EXT
  NULL,                                   // Get Event Log command
  NULL,                                   // Publish Event Log command
#endif
  NULL,                                   // RSSI Location command
  NULL                                    // RSSI Location Response command
};

/*********************************************************************
 * @fn          zclSampleSw_Init
 *
 * @brief       Initialization function for the zclGeneral layer.
 *
 * @param       none
 *
 * @return      none
 */
void zclSampleSw_Init( byte task_id )
{
  zclSampleSw_TaskID = task_id;

  // Set destination address to indirect
  zclSampleSw_DstAddr.addrMode = (afAddrMode_t)AddrNotPresent;
  zclSampleSw_DstAddr.endPoint = 0;
  zclSampleSw_DstAddr.addr.shortAddr = 0;

  // Register the Simple Descriptor for this application
  bdb_RegisterSimpleDescriptor( &zclSampleSw_SimpleDesc );

  // Register the ZCL General Cluster Library callback functions
  zclGeneral_RegisterCmdCallbacks( SAMPLESW_ENDPOINT, &zclSampleSw_CmdCallbacks );

  zclSampleSw_ResetAttributesToDefaultValues();
  
  // Register the application's attribute list
  zcl_registerAttrList( SAMPLESW_ENDPOINT, zclSampleSw_NumAttributes, zclSampleSw_Attrs );

  // Register the Application to receive the unprocessed Foundation command/response messages
  zcl_registerForMsg( zclSampleSw_TaskID );
  
  // Keep the original P0.1/S1 key handling.
  RegisterForKeys( zclSampleSw_TaskID );
  
  bdb_RegisterCommissioningStatusCB( zclSampleSw_ProcessCommissioningStatus );

  // Register for a test endpoint
  afRegister( &sampleSw_TestEp );

  // Register private endpoint 1 used to send sensor data to the gateway.
  afRegister( &ebikePort01Ep );
  
#ifdef ZCL_DIAGNOSTIC
  // Register the application's callback function to read/write attribute data.
  // This is only required when the attribute data format is unknown to ZCL.
  zcl_registerReadWriteCB( SAMPLESW_ENDPOINT, zclDiagnostic_ReadWriteAttrCB, NULL );

  if ( zclDiagnostic_InitStats() == ZSuccess )
  {
    // Here the user could start the timer to save Diagnostics to NV
  }
#endif

#if defined (OTA_CLIENT) && (OTA_CLIENT == TRUE)
  // Register for callback events from the ZCL OTA
  zclOTA_Register(zclSampleSw_TaskID);
#endif

  zdpExternalStateTaskID = zclSampleSw_TaskID;

  // Init Uart
  zclSampleSw_InitUart();

  // Environment terminal: DHT11 data=P0.6, light ADC=P0.7, pressure ADC=P0.0.
  P0SEL &= ~BV(5);
  P0DIR |= BV(5);
  P0_5 = 0;
  // Active-low buzzer IO=P0.2; D2=P0.4 mirrors the commanded state.
  P0SEL &= ~BV(2);
  P0DIR |= BV(2);
  P0_2 = 1;
  P0SEL &= ~BV(4);
  P0DIR |= BV(4);
  P0_4 = 0;
  envDht11SetIdle();
  // Local sensor display keeps working even while Zigbee is offline.
  osal_start_timerEx(zclSampleSw_TaskID,
                     SENSOR_REPORT_EVT,
                     bandwidthPeriodMs);
#ifdef ZDO_COORDINATOR
  bdb_StartCommissioning( BDB_COMMISSIONING_MODE_NWK_FORMATION |
                          BDB_COMMISSIONING_MODE_FINDING_BINDING );
  
  NLME_PermitJoiningRequest(255);
#else
  bdb_StartCommissioning( BDB_COMMISSIONING_MODE_NWK_STEERING );
#endif
}

/*********************************************************************
 * @fn          zclSample_event_loop
 *
 * @brief       Event Loop Processor for zclGeneral.
 *
 * @param       none
 *
 * @return      none
 */
uint16 zclSampleSw_event_loop( uint8 task_id, uint16 events )
{
  afIncomingMSGPacket_t *MSGpkt;
  (void)task_id;  // Intentionally unreferenced parameter

  //Send toggle every 500ms
  if( events & SAMPLESW_TOGGLE_TEST_EVT )
  {
    zclGeneral_SendOnOff_CmdToggle( SAMPLESW_ENDPOINT, &zclSampleSw_DstAddr, FALSE, 0 );
    
    // return unprocessed events
    return (events ^ SAMPLESW_TOGGLE_TEST_EVT);
  }
  
  
  if ( events & SYS_EVENT_MSG )
  {
    while ( (MSGpkt = (afIncomingMSGPacket_t *)osal_msg_receive( zclSampleSw_TaskID )) )
    {
      switch ( MSGpkt->hdr.event )
      {
        case AF_INCOMING_MSG_CMD:
          zclSampleSw_ProcessDownlink(MSGpkt);
          break;

        case ZCL_INCOMING_MSG:
          // Incoming ZCL Foundation command/response messages
          zclSampleSw_ProcessIncomingMsg( (zclIncomingMsg_t *)MSGpkt );
          break;

        case KEY_CHANGE:
          zclSampleSw_HandleKeys( ((keyChange_t *)MSGpkt)->state, ((keyChange_t *)MSGpkt)->keys );
          break;

        case ZDO_STATE_CHANGE:
          zclSampleSw_NwkState = (devStates_t)(MSGpkt->hdr.status);
          break;

#if defined (OTA_CLIENT) && (OTA_CLIENT == TRUE)
        case ZCL_OTA_CALLBACK_IND:
          zclSampleSw_ProcessOTAMsgs( (zclOTA_CallbackMsg_t*)MSGpkt  );
          break;
#endif

        default:
          break;
      }

      // Release the memory
      osal_msg_deallocate( (uint8 *)MSGpkt );
    }

    // return unprocessed events
    return (events ^ SYS_EVENT_MSG);
  }

#if ZG_BUILD_ENDDEVICE_TYPE    
  if ( events & SAMPLEAPP_END_DEVICE_REJOIN_EVT )
  {
    bdb_ZedAttemptRecoverNwk();
    return ( events ^ SAMPLEAPP_END_DEVICE_REJOIN_EVT );
  }
#endif
  
  // Test Event
  if ( events & SAMPLEAPP_TEST_EVT )
  {
    uint8 *pMem;
    
    pMem = osal_mem_alloc(100);
    if(pMem != NULL)
    {
      osal_memset( pMem, 0, 100 );
      osal_memcpy( pMem, "Hello World!", 12 );
    }
    
    printf("%s\r\n", pMem);
    
    osal_mem_free(pMem);
    
    osal_start_timerEx(zclSampleSw_TaskID, 
                     SAMPLEAPP_TEST_EVT, 
                     3000);
    
    return ( events ^ SAMPLEAPP_TEST_EVT );
  }
  
  // Rejoin
#ifdef ZDO_COORDINATOR
#else
  if ( events & SAMPLEAPP_REJOIN_EVT )
  {
   bdb_StartCommissioning(BDB_COMMISSIONING_MODE_NWK_STEERING);
    
    return ( events ^ SAMPLEAPP_REJOIN_EVT );
  }
#endif
  // Router Rejoin - ���ڵ㶪ʧ������
  #if ZG_BUILD_ROUTER_TYPE
    if ( events & SAMPLEAPP_ROUTER_REJOIN_EVT )
    {
      bdb_StartCommissioning(BDB_COMMISSIONING_MODE_NWK_STEERING);
      return ( events ^ SAMPLEAPP_ROUTER_REJOIN_EVT );
    }
  #endif
  // ��λ��ʱ�¼�
    // Legacy key code schedules 0x000A.  Require an exact match so unrelated
    // 0x0002/0x0008 events can never trigger a software reset.
    if ( events == SAMPLESW_FACTORY_RESET_EVT )
    {
      P0_4 = !P0_4;
      return (events ^ SAMPLESW_FACTORY_RESET_EVT);
    }
  // Discard unknown events
  // �����������ϱ��¼�
     // �����������ϱ��¼�
    if ( events & SENSOR_REPORT_EVT )
    {
      char lcdBuf[17];
      static uint8 zclSeq = 0;
      static uint32 sequence = 0;
      static uint16 acceptedCount = 0;
      static uint16 rejectedCount = 0;
      uint8 sensorData[37];
      uint8 i;
      afAddrType_t destAddr;
      afStatus_t txStatus;

      HalLcdWriteStringValue("BW STAGE:", bandwidthStage, 10, HAL_LCD_LINE_1);
      if (bandwidthPeriodMs == 0)
        sprintf(lcdBuf, "PERIOD:PAUSE");
      else
        sprintf(lcdBuf, "PERIOD:%dms", (int)bandwidthPeriodMs);
      HalLcdWriteString(lcdBuf, HAL_LCD_LINE_2);
      HalLcdWriteStringValue("SEQ:", (uint16)sequence, 10, HAL_LCD_LINE_3);

      // Use Z-Stack's live state; the application state-change message may
      // arrive late while commissioning or recovering a parent.
      if (devState != DEV_END_DEVICE)
      {
        HalLcdWriteString("NET:OFFLINE", HAL_LCD_LINE_4);
        if (bandwidthPeriodMs != 0)
        {
          osal_start_timerEx(zclSampleSw_TaskID,
                             SENSOR_REPORT_EVT,
                             bandwidthPeriodMs);
        }
        return (events ^ SENSOR_REPORT_EVT);
      }

      // EBYTE manufacturer-specific ZCL command:
      // frame control, manufacturer code 0x2000, ZCL sequence, UartSend cmd 0x00.
      sensorData[0] = 0x15;
      sensorData[1] = 0x00;
      sensorData[2] = 0x20;
      sensorData[3] = zclSeq++;
      sensorData[4] = 0x00;

      // 32-byte bandwidth-test application payload.
      sensorData[5]  = 0xB0;
      sensorData[6]  = 0x02;
      sensorData[7]  = 0x01;
      sensorData[8]  = bandwidthStage;
      sensorData[9]  = LO_UINT16(bandwidthPeriodMs);
      sensorData[10] = HI_UINT16(bandwidthPeriodMs);
      sensorData[11] = (uint8)(sequence);
      sensorData[12] = (uint8)(sequence >> 8);
      sensorData[13] = (uint8)(sequence >> 16);
      sensorData[14] = (uint8)(sequence >> 24);
      sensorData[15] = LO_UINT16(acceptedCount);
      sensorData[16] = HI_UINT16(acceptedCount);
      sensorData[17] = LO_UINT16(rejectedCount);
      sensorData[18] = HI_UINT16(rejectedCount);
      for (i = 19; i < sizeof(sensorData); i++)
      {
        sensorData[i] = i;
      }

      // Coordinator always has network short address 0x0000.
      destAddr.addrMode = (afAddrMode_t)Addr16Bit;
      destAddr.endPoint = 0x01;
      destAddr.addr.shortAddr = 0x0000;

      txStatus = AF_DataRequest(&destAddr,
                                &ebikePort01Ep,
                                EBYTE_TRANSPARENT_CLUSTER_ID,
                                sizeof(sensorData),
                                sensorData,
                                &zclSampleSw_AfTransId,
                                AF_DISCV_ROUTE,
                                AF_DEFAULT_RADIUS);

      if (txStatus == afStatus_SUCCESS)
      {
        acceptedCount++;
        HalLcdWriteString("NET:TX OK", HAL_LCD_LINE_4);
      }
      else
      {
        rejectedCount++;
        HalLcdWriteStringValue("TX FAIL:", txStatus, 16, HAL_LCD_LINE_4);
      }
      sequence++;

      if (bandwidthPeriodMs != 0)
      {
        osal_start_timerEx(zclSampleSw_TaskID,
                           SENSOR_REPORT_EVT,
                           bandwidthPeriodMs);
      }
      return (events ^ SENSOR_REPORT_EVT);
    }

#if 0  // Old fixed test-packet sender; disabled for the ADC-only minimum demo.
    if ( events & SENSOR_REPORT_EVT )
    {
      static uint8 transID = 0;
      uint8 sensorData[6];
      sensorData[0] = 0x15;       // Frame Control: cluster-specific, client->server, no default response
      sensorData[1] = transID++;   // Transaction Sequence Number
      sensorData[2] = 0x00;       // Command ID (cluster-specific)
      sensorData[3] = '2';
      sensorData[4] = '3';
      sensorData[5] = '4';

      afAddrType_t destAddr;
      destAddr.addrMode = (afAddrMode_t)Addr16Bit;  // 单播模式
      destAddr.endPoint = 0x01;                      // 目标端口01
      destAddr.addr.shortAddr = 0x0000;              // 直接发给协调器

      // 发送数据到协调器
      AF_DataRequest(&destAddr,
                     &ebikePort01Ep,           // 使用端点为1的描述符
                     0x0000,                   // 簇ID
                     6,
                     sensorData,
                     &transID,
                     AF_DISCV_ROUTE,
                     AF_DEFAULT_RADIUS);

      osal_start_timerEx(zclSampleSw_TaskID, SENSOR_REPORT_EVT, 30);
      return (events ^ SENSOR_REPORT_EVT);
    }
#endif
  return 0;
}

/*********************************************************************
 * @fn      zclSampleSw_HandleKeys
 *
 * @brief   Handles all key events for this device.
 *
 * @param   shift - true if in shift/alt.
 * @param   keys - bit field for key events. Valid entries:
 *                 HAL_KEY_SW_5
 *                 HAL_KEY_SW_4
 *                 HAL_KEY_SW_2
 *                 HAL_KEY_SW_1
 *
 * @return  none
 */
static uint16 zclSampleSw_BandwidthPeriodForStage(uint8 stage)
{
  switch (stage)
  {
    case 0: return 1000;
    case 1: return 500;
    case 2: return 200;
    case 3: return 100;
    case 4: return 50;
    case 5: return 20;
    case 6: return 10;
    default: return 0;
  }
}

static void zclSampleSw_HandleKeys( byte shift, byte keys )
{ 
  char lcdBuf[17];

  if(keys & HAL_KEY_SW_6)
  {
    // ���������Ϣ��ǿ����������
    bandwidthStage = (bandwidthStage + 1) & 0x07;
    bandwidthPeriodMs = zclSampleSw_BandwidthPeriodForStage(bandwidthStage);
    osal_stop_timerEx(zclSampleSw_TaskID, SENSOR_REPORT_EVT);
    if (bandwidthPeriodMs != 0)
    {
      osal_start_timerEx(zclSampleSw_TaskID, SENSOR_REPORT_EVT, 10);
    }

    // ��ʾ��ʾ
    HalLcdWriteStringValue("BW STAGE:", bandwidthStage, 10, HAL_LCD_LINE_1);
    if (bandwidthPeriodMs == 0)
      HalLcdWriteString("PERIOD:PAUSE", HAL_LCD_LINE_2);
    else
    {
      sprintf(lcdBuf, "PERIOD:%dms", (int)bandwidthPeriodMs);
      HalLcdWriteString(lcdBuf, HAL_LCD_LINE_2);
    }

    // ��ʱ��λ���� NV д���㹻ʱ��
    osal_start_timerEx(zclSampleSw_TaskID, 10, 1);  // 10ms �󴥷�
  }
}
  
/*********************************************************************
 * @fn      zclSampleSw_ProcessCommissioningStatus
 *
 * @brief   Callback in which the status of the commissioning process are reported
 *
 * @param   bdbCommissioningModeMsg - Context message of the status of a commissioning process
 *
 * @return  none
 */
static void zclSampleSw_ProcessCommissioningStatus(bdbCommissioningModeMsg_t *bdbCommissioningModeMsg)
{
  switch(bdbCommissioningModeMsg->bdbCommissioningMode)
  {
    case BDB_COMMISSIONING_FORMATION:
      if(bdbCommissioningModeMsg->bdbCommissioningStatus == BDB_COMMISSIONING_SUCCESS)
      {
        //After formation, perform nwk steering again plus the remaining commissioning modes that has not been processed yet
        bdb_StartCommissioning(BDB_COMMISSIONING_MODE_NWK_STEERING | bdbCommissioningModeMsg->bdbRemainingCommissioningModes);
      }
      else
      {
        //Want to try other channels?
        //try with bdb_setChannelAttribute
      }
    break;
    case BDB_COMMISSIONING_NWK_STEERING:
      if(bdbCommissioningModeMsg->bdbCommissioningStatus == BDB_COMMISSIONING_SUCCESS)
      {
        //YOUR JOB:
        //We are on the nwk, what now?

      }
      else
      {
        #ifdef ZDO_COORDINATOR
        #else
        osal_start_timerEx(zclSampleSw_TaskID, 
                           SAMPLEAPP_REJOIN_EVT, 
                           SAMPLEAPP_REJOIN_PERIOD);
        #endif
         
        //See the possible errors for nwk steering procedure
        //No suitable networks found
        //Want to try other channels?
        //try with bdb_setChannelAttribute
      }
    break;
    case BDB_COMMISSIONING_FINDING_BINDING:
      if(bdbCommissioningModeMsg->bdbCommissioningStatus == BDB_COMMISSIONING_SUCCESS)
      {
        //YOUR JOB:
      }
      else
      {
        //YOUR JOB:
        //retry?, wait for user interaction?
      }
    break;
    case BDB_COMMISSIONING_INITIALIZATION:
      //Initialization notification can only be successful. Failure on initialization 
      //only happens for ZED and is notified as BDB_COMMISSIONING_PARENT_LOST notification
      
      //YOUR JOB:
      //We are on a network, what now?
      
    break;
#if ZG_BUILD_ENDDEVICE_TYPE    
    case BDB_COMMISSIONING_PARENT_LOST:
      if(bdbCommissioningModeMsg->bdbCommissioningStatus == BDB_COMMISSIONING_NETWORK_RESTORED)
      {
//We did recover from losing parent
      }
      else
      {
//Parent not found, attempt to rejoin again after a fixed delay
        osal_start_timerEx(zclSampleSw_TaskID, SAMPLEAPP_END_DEVICE_REJOIN_EVT, SAMPLEAPP_END_DEVICE_REJOIN_DELAY);
      }
    break;
#endif 
#if ZG_BUILD_ROUTER_TYPE
      case BDB_COMMISSIONING_PARENT_LOST:
        if(bdbCommissioningModeMsg->bdbCommissioningStatus == BDB_COMMISSIONING_NETWORK_RESTORED)
        {
          //We did recover from losing parent
        }
        else
        {
          //Parent not found, attempt to rejoin again after a fixed delay
          osal_start_timerEx(zclSampleSw_TaskID,
                             SAMPLEAPP_ROUTER_REJOIN_EVT,
                             SAMPLEAPP_ROUTER_REJOIN_DELAY);
        }
        break;
  #endif
  }
}

/*********************************************************************
 * @fn      zclSampleSw_BasicResetCB
 *
 * @brief   Callback from the ZCL General Cluster Library
 *          to set all the Basic Cluster attributes to  default values.
 *
 * @param   none
 *
 * @return  none
 */
static void zclSampleSw_BasicResetCB( void )
{
  zclSampleSw_ResetAttributesToDefaultValues();
}

/******************************************************************************
 *
 *  Functions for processing ZCL Foundation incoming Command/Response messages
 *
 *****************************************************************************/

/*********************************************************************
 * @fn      zclSampleSw_ProcessIncomingMsg
 *
 * @brief   Process ZCL Foundation incoming message
 *
 * @param   pInMsg - pointer to the received message
 *
 * @return  none
 */
static void zclSampleSw_ProcessIncomingMsg( zclIncomingMsg_t *pInMsg )
{
  switch ( pInMsg->zclHdr.commandID )
  {
#ifdef ZCL_READ
    case ZCL_CMD_READ_RSP:
      zclSampleSw_ProcessInReadRspCmd( pInMsg );
      break;
#endif
#ifdef ZCL_WRITE
    case ZCL_CMD_WRITE_RSP:
      zclSampleSw_ProcessInWriteRspCmd( pInMsg );
      break;
#endif
#ifdef ZCL_REPORT
    // See ZCL Test Applicaiton (zcl_testapp.c) for sample code on Attribute Reporting
    case ZCL_CMD_CONFIG_REPORT:
      //zclSampleSw_ProcessInConfigReportCmd( pInMsg );
      break;

    case ZCL_CMD_CONFIG_REPORT_RSP:
      //zclSampleSw_ProcessInConfigReportRspCmd( pInMsg );
      break;

    case ZCL_CMD_READ_REPORT_CFG:
      //zclSampleSw_ProcessInReadReportCfgCmd( pInMsg );
      break;

    case ZCL_CMD_READ_REPORT_CFG_RSP:
      //zclSampleSw_ProcessInReadReportCfgRspCmd( pInMsg );
      break;

    case ZCL_CMD_REPORT:
      //zclSampleSw_ProcessInReportCmd( pInMsg );
      break;
#endif
    case ZCL_CMD_DEFAULT_RSP:
      zclSampleSw_ProcessInDefaultRspCmd( pInMsg );
      break;
#ifdef ZCL_DISCOVER
    case ZCL_CMD_DISCOVER_CMDS_RECEIVED_RSP:
      zclSampleSw_ProcessInDiscCmdsRspCmd( pInMsg );
      break;

    case ZCL_CMD_DISCOVER_CMDS_GEN_RSP:
      zclSampleSw_ProcessInDiscCmdsRspCmd( pInMsg );
      break;

    case ZCL_CMD_DISCOVER_ATTRS_RSP:
      zclSampleSw_ProcessInDiscAttrsRspCmd( pInMsg );
      break;

    case ZCL_CMD_DISCOVER_ATTRS_EXT_RSP:
      zclSampleSw_ProcessInDiscAttrsExtRspCmd( pInMsg );
      break;
#endif
    default:
      break;
  }

  if ( pInMsg->attrCmd )
    osal_mem_free( pInMsg->attrCmd );
}

#ifdef ZCL_READ
/*********************************************************************
 * @fn      zclSampleSw_ProcessInReadRspCmd
 *
 * @brief   Process the "Profile" Read Response Command
 *
 * @param   pInMsg - incoming message to process
 *
 * @return  none
 */
static uint8 zclSampleSw_ProcessInReadRspCmd( zclIncomingMsg_t *pInMsg )
{
  zclReadRspCmd_t *readRspCmd;
  uint8 i;

  readRspCmd = (zclReadRspCmd_t *)pInMsg->attrCmd;
  for (i = 0; i < readRspCmd->numAttr; i++)
  {
    // Notify the originator of the results of the original read attributes
    // attempt and, for each successfull request, the value of the requested
    // attribute
  }

  return TRUE;
}
#endif // ZCL_READ

#ifdef ZCL_WRITE
/*********************************************************************
 * @fn      zclSampleSw_ProcessInWriteRspCmd
 *
 * @brief   Process the "Profile" Write Response Command
 *
 * @param   pInMsg - incoming message to process
 *
 * @return  none
 */
static uint8 zclSampleSw_ProcessInWriteRspCmd( zclIncomingMsg_t *pInMsg )
{
  zclWriteRspCmd_t *writeRspCmd;
  uint8 i;

  writeRspCmd = (zclWriteRspCmd_t *)pInMsg->attrCmd;
  for (i = 0; i < writeRspCmd->numAttr; i++)
  {
    // Notify the device of the results of the its original write attributes
    // command.
  }

  return TRUE;
}
#endif // ZCL_WRITE

/*********************************************************************
 * @fn      zclSampleSw_ProcessInDefaultRspCmd
 *
 * @brief   Process the "Profile" Default Response Command
 *
 * @param   pInMsg - incoming message to process
 *
 * @return  none
 */
static uint8 zclSampleSw_ProcessInDefaultRspCmd( zclIncomingMsg_t *pInMsg )
{
  // zclDefaultRspCmd_t *defaultRspCmd = (zclDefaultRspCmd_t *)pInMsg->attrCmd;
  // Device is notified of the Default Response command.
  (void)pInMsg;
  return TRUE;
}

#ifdef ZCL_DISCOVER
/*********************************************************************
 * @fn      zclSampleSw_ProcessInDiscCmdsRspCmd
 *
 * @brief   Process the Discover Commands Response Command
 *
 * @param   pInMsg - incoming message to process
 *
 * @return  none
 */
static uint8 zclSampleSw_ProcessInDiscCmdsRspCmd( zclIncomingMsg_t *pInMsg )
{
  zclDiscoverCmdsCmdRsp_t *discoverRspCmd;
  uint8 i;

  discoverRspCmd = (zclDiscoverCmdsCmdRsp_t *)pInMsg->attrCmd;
  for ( i = 0; i < discoverRspCmd->numCmd; i++ )
  {
    // Device is notified of the result of its attribute discovery command.
  }

  return TRUE;
}

/*********************************************************************
 * @fn      zclSampleSw_ProcessInDiscAttrsRspCmd
 *
 * @brief   Process the "Profile" Discover Attributes Response Command
 *
 * @param   pInMsg - incoming message to process
 *
 * @return  none
 */
static uint8 zclSampleSw_ProcessInDiscAttrsRspCmd( zclIncomingMsg_t *pInMsg )
{
  zclDiscoverAttrsRspCmd_t *discoverRspCmd;
  uint8 i;

  discoverRspCmd = (zclDiscoverAttrsRspCmd_t *)pInMsg->attrCmd;
  for ( i = 0; i < discoverRspCmd->numAttr; i++ )
  {
    // Device is notified of the result of its attribute discovery command.
  }

  return TRUE;
}

/*********************************************************************
 * @fn      zclSampleSw_ProcessInDiscAttrsExtRspCmd
 *
 * @brief   Process the "Profile" Discover Attributes Extended Response Command
 *
 * @param   pInMsg - incoming message to process
 *
 * @return  none
 */
static uint8 zclSampleSw_ProcessInDiscAttrsExtRspCmd( zclIncomingMsg_t *pInMsg )
{
  zclDiscoverAttrsExtRsp_t *discoverRspCmd;
  uint8 i;

  discoverRspCmd = (zclDiscoverAttrsExtRsp_t *)pInMsg->attrCmd;
  for ( i = 0; i < discoverRspCmd->numAttr; i++ )
  {
    // Device is notified of the result of its attribute discovery command.
  }

  return TRUE;
}
#endif // ZCL_DISCOVER

#if defined (OTA_CLIENT) && (OTA_CLIENT == TRUE)
/*********************************************************************
 * @fn      zclSampleSw_ProcessOTAMsgs
 *
 * @brief   Called to process callbacks from the ZCL OTA.
 *
 * @param   none
 *
 * @return  none
 */
static void zclSampleSw_ProcessOTAMsgs( zclOTA_CallbackMsg_t* pMsg )
{
  uint8 RxOnIdle;

  switch(pMsg->ota_event)
  {
  case ZCL_OTA_START_CALLBACK:
    if (pMsg->hdr.status == ZSuccess)
    {
      // Speed up the poll rate
      RxOnIdle = TRUE;
      ZMacSetReq( ZMacRxOnIdle, &RxOnIdle );
      NLME_SetPollRate( 2000 );
    }
    break;

  case ZCL_OTA_DL_COMPLETE_CALLBACK:
    if (pMsg->hdr.status == ZSuccess)
    {
      // Reset the CRC Shadow and reboot.  The bootloader will see the
      // CRC shadow has been cleared and switch to the new image
      HalOTAInvRC();
      SystemReset();
    }
    else
    {
      // slow the poll rate back down.
      RxOnIdle = FALSE;
      ZMacSetReq( ZMacRxOnIdle, &RxOnIdle );
      NLME_SetPollRate(DEVICE_POLL_RATE);
    }
    break;

  default:
    break;
  }
}
#endif // defined (OTA_CLIENT) && (OTA_CLIENT == TRUE)

/****************************************************************************
****************************************************************************/

/**
 * @fn      zclSampleSw_InitUart
 *
 * @brief   init. and open Uart
 */
static void zclSampleSw_InitUart(void)
{
  halUARTCfg_t uartConfig;

  /* UART Configuration */
  uartConfig.configured           = TRUE;
  uartConfig.baudRate             = HAL_UART_BR_115200;
  uartConfig.flowControl          = FALSE;
  uartConfig.flowControlThreshold = 0;
  uartConfig.rx.maxBufSize        = ZCLSAMPLESW_UART_BUF_LEN;
  uartConfig.tx.maxBufSize        = 0;
  uartConfig.idleTimeout          = 6;
  uartConfig.intEnable            = TRUE;
  uartConfig.callBackFunc         = zclSampleSw_UartCB;

  /* Start UART */
  HalUARTOpen(HAL_UART_PORT_0, &uartConfig);
}

/**
 * @fn      zclSampleSw_UartCB
 *
 * @brief   Uart Callback
 */
static void zclSampleSw_UartCB(uint8 port, uint8 event)
{
  uint8 rxLen = Hal_UART_RxBufLen(HAL_UART_PORT_0);

  if(rxLen != 0)
  {
    HalUARTRead(HAL_UART_PORT_0  ,  zclSampleSw_UartBuf , rxLen);
    HalUARTWrite(HAL_UART_PORT_0 ,  zclSampleSw_UartBuf , rxLen);
  }
}
