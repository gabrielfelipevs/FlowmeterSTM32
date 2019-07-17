/*
 * cmh.h
 *
 *  Created on: 15 de abr de 2019
 *      Author: Marcelo
 */

#ifndef CMD_H_
#define CMD_H_

#define CMD_MAX_SIZE 256
#define CMD_HDR_SIZE 4
#define CMD_TRL_SIZE 2
#define CMD_MAX_TOTAL_BUF (CMD_HDR_SIZE+CMD_MAX_SIZE+CMD_TRL_SIZE)
#define CMD_DEV_ADDR 10

#define CMD_ITF_VER          0x00
#define CMD_IDENT            0x01
#define CMD_POINT_DESC_BASE  0x10
#define CMD_POINT_READ_BASE  0x30
#define CMD_POINT_WRITE_BASE 0x50

//Check Point


#define CMD_POINT_READ_ONLY 0x00
#define CMD_POINT_WRITE_ONLY 0x01
#define CMD_POINT_READ_WRITE 0x02


#define CMD_IDENT_MANUFACTER "FLOWMETR"
#define CMD_IDENT_MODEL   "GABRIELF"
#define CMD_IDENT_ID 0x01
#define CMD_IDENT_REV 0x01
#define CMD_IDENT_POINT 0x03 // NUMERO DE I/O

//FIM


#define CMD_VERSION 1

#define FRAME_FLAG 0x7E
#define FRAME_ESC  0x7D

typedef struct cmd_s
{
    uint8_t dst;
    uint8_t src;
    uint8_t reg;
    uint8_t size;
    uint8_t payload[CMD_MAX_SIZE];
    uint16_t crc;
    volatile uint16_t rx_bytes;
} cmd_t;

typedef union frame_u
{
    cmd_t cmd;
    uint8_t buffer[CMD_MAX_TOTAL_BUF];
} frame_t;

typedef union point_values_u
{
    uint8_t u8;
    int8_t i8;
    uint16_t u16;
    int16_t i16;
    float f;
} point_values_t;

typedef struct point_db_s
{
    uint8_t name[8];
    uint8_t type;
    uint8_t unit;
    point_values_t value;
} point_db_t;

// point_db_t db[4];
// db[0].value.f = 3.1415;
// db[0].value.u16 = 123;

#endif /* CMD_H_ */
