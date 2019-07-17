/*
 * app.c
 *
 *  Created on: 15 de abr de 2019
 *      Author: GABRIEL FELIPE
 *      gabrielfelipe9@hotmail.com
 */
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
#include "cmd.h"
#include "app.h"
#include "hw.h"
#include "crc16.h"
#include "stm32f1xx_hal.h"
#include "main.h"
#include "i2c-lcd.h"
#include "buf_io.h"

volatile bool app_new_frame;
frame_t frame;
uint8_t new_frame = 0;
frame_t frame;
uint8_t TxCmpl;
volatile uint8_t salvedst;

// VARIAVEIS DO PROCESSO
volatile uint16_t pulses = 0; // count pulses
volatile uint8_t lastflowpinstate; // monitora o status do pino FLOWSENSORPIN
volatile GPIO_PinState lastflowratetimer = 0; // contando o tempo entre os pulsos
volatile float flowrate; // calcula a taxa de fluxo
volatile float liters = 0;
uint8_t out_liters = 0;
//char send_liters;
volatile char send_pulses[1];
char send_liters[4];
float liters_rounded_down;
float cur_liters = 0;
volatile uint16_t conta_litro = 0;
uint8_t conta_litro_AUX = 0;
char send_conta[5];
extern TIM_HandleTypeDef htim2;
static void write_lcd(void);
uint32_t debounce = 0;
uint32_t debounce2 = 0;
uint32_t debounce3 = 0;
volatile GPIO_PinState Rele_ON = 0;
volatile bool app_started = false;


bool app_add_received_byte(uint8_t b)
{
	static bool buffer_esc = false;

	if ((frame.cmd.rx_bytes == 0) && (b == FRAME_FLAG))
		return 0;

	if ((!buffer_esc) && (b == FRAME_ESC))
	{
		buffer_esc = true;
		return false;
	}

	if ((!buffer_esc) && (b == FRAME_FLAG))
		return true;

	if (frame.cmd.rx_bytes >= CMD_MAX_SIZE)
	{
		frame.cmd.rx_bytes = 0;
		buffer_esc = false;
		return false;
	}

	frame.buffer[frame.cmd.rx_bytes++] = b;

	if (buffer_esc == 1)
		buffer_esc = false;

	return false;
}

static bool app_check_frame(frame_t *frame)
{
	uint16_t crc;

	if(frame->cmd.rx_bytes < CMD_HDR_SIZE)
		return false;

	if(frame->cmd.dst != CMD_DEV_ADDR)
		return false;

	if(frame->cmd.size != (frame->cmd.rx_bytes - CMD_HDR_SIZE - CMD_TRL_SIZE))
		return false;

	crc = (frame->buffer[frame->cmd.rx_bytes-2] << 8) | (frame->buffer[frame->cmd.rx_bytes-1]) ;

	frame->cmd.crc = crc16_calc(frame->buffer, CMD_HDR_SIZE+frame->cmd.size);

	if(crc != frame->cmd.crc)
		return false;

	return true;
}

static void app_send_frame(frame_t *frame)
{

	uint16_t n;

	hw_rx_enable(false);

	hw_delay(2);

	hw_uart_send_byte(FRAME_FLAG,0);

	for (n=0 ; n < (CMD_HDR_SIZE + frame->cmd.size) ; n++)
		hw_uart_send_byte(frame->buffer[n], 1);

	hw_uart_send_byte(frame->cmd.crc >> 8 ,1);
	hw_uart_send_byte(frame->cmd.crc & 0XFF ,1);

	hw_uart_send_byte(FRAME_FLAG, 0);

	hw_delay(2);

	hw_rx_enable(true);

}

void app_decode_and_answer_version(frame_t *frame)
{
	uint8_t c;

	c = frame->cmd.dst;
	frame->cmd.dst = frame->cmd.src;
	frame->cmd.src = c;

	frame->cmd.payload[0] = CMD_VERSION;
	frame->cmd.size = 1;

	frame->cmd.crc = crc16_calc(frame->buffer, CMD_HDR_SIZE+frame->cmd.size);

	app_send_frame(frame);
}


void app_decode_and_answer_ident(frame_t *frame)
{
	uint8_t c;
	char buffer[20] = {0};

	// troca dst/src
	c = frame->cmd.dst;
	frame->cmd.dst = frame->cmd.src;
	frame->cmd.src = c;

	memset(&frame->cmd.payload[0],' ',8);
	strncpy(&frame->cmd.payload[0],CMD_IDENT_MANUFACTER,8);  // ajusta o tamanho
	frame->cmd.size = 22; //tamanho do payload
	strcat(buffer,CMD_IDENT_MANUFACTER);
	strcat(buffer,CMD_IDENT_MODEL);
	memcpy(frame->cmd.payload,buffer,16);

	frame->cmd.payload[16] = 0X00;
	frame->cmd.payload[17] = 0X00;
	frame->cmd.payload[18] = 0X00;
	frame->cmd.payload[19] = CMD_IDENT_ID;

    // informa as identificoes
	frame->cmd.payload[20] = CMD_IDENT_REV;
	frame->cmd.payload[21] = CMD_IDENT_POINT;


	frame->cmd.crc = crc16_calc(frame->buffer,CMD_HDR_SIZE + frame->cmd.size); //CRC

	TxCmpl =  1;
	app_send_frame(frame);
}

void app_decode_and_answer_desc(frame_t *frame)
{
	uint8_t aux;

	aux = frame->cmd.dst;
	frame->cmd.dst = frame->cmd.src;
	frame->cmd.src = aux;
	frame->cmd.size = 11;

	if( frame->cmd.reg == 16)
	{
		memcpy(frame->cmd.payload,"SETLITRO",sizeof("SETLITRO"));
		frame->cmd.payload[8] =  0x02; //TYPE  8 bits unsigned
		frame->cmd.payload[9] = 41;// LITERS
		frame->cmd.payload[10] = 0x02;// Access Rights
	}

	else if( frame->cmd.reg == 17)
	{
		memset(&frame->cmd.payload,' ',8);
		strncpy(&frame->cmd.payload,"ON_OFF",8);  // ajusta o tamanho
		frame->cmd.payload[8] =  0x00; //TYPE  8 bits unsigned
		frame->cmd.payload[9] = 251; //SEM UNIDADE
		frame->cmd.payload[10] = 0x00;// Access Rights
	}
	else if ( frame->cmd.reg == 18 )
	{
		memset(&frame->cmd.payload,' ',8);
		strncpy(&frame->cmd.payload,"LITROS",8);  // ajusta o tamanho
		frame->cmd.payload[8] = 0x08; //TYPE: Float, IEEE 754 single precision, 4 bytes
		frame->cmd.payload[9] = 41; // LITERS
		frame->cmd.payload[10] = 0x00;// Access Rights

	}

	frame->cmd.crc = crc16_calc(frame->buffer,CMD_HDR_SIZE + frame->cmd.size);

	app_send_frame(frame);
}

void app_decode_and_answer_read(frame_t *frame)
{

	salvedst = frame->cmd.dst; //salva o destino
	frame->cmd.dst = frame->cmd.src; // troca dst/src
	frame->cmd.src = salvedst; //coloca o destino na origem

	if ( frame->cmd.reg == 48 )
	{

		frame->cmd.size = 3;

		frame->cmd.payload[0] = 0x02; //TYPE Short, 16 bits unsigned
		frame->cmd.payload[1] = (conta_litro>>8);
		frame->cmd.payload[2] = (conta_litro);
	}
	else if ( frame->cmd.reg == 49 )
	{
		frame->cmd.size = 2;
		frame->cmd.payload[0] = 0x00; //TYPE Byte, 8 bits unsigned
		frame->cmd.payload[1] = (uint8_t) Rele_ON;

	}
	else if ( frame->cmd.reg == 50 )
	{
		  frame->cmd.size = 5;
		  uint8_t *pbuf;
		  pbuf = frame->cmd.payload;
		  buf_io_put8_tb_ap(0X08,pbuf);
		  buf_io_putf_tb_ap(liters,pbuf);

	}

	frame->cmd.crc = crc16_calc(frame->buffer,CMD_HDR_SIZE + frame->cmd.size);

	app_send_frame(frame);
}

void app_decode_and_answer_write(frame_t *frame)
{
	salvedst = frame->cmd.dst;
	frame->cmd.dst = frame->cmd.src;
	frame->cmd.src = salvedst;
	frame->cmd.size = 0;

	if ( frame->cmd.reg == 80 )
		{
			frame->cmd.payload[0] = 0x02; //TYPE Short, 16 bits unsigned
			//(conta_litro>>8) = frame->cmd.payload[1];
			//conta_litro = frame->cmd.payload[1];
			//conta_litro = frame->cmd.payload[1];
			conta_litro = frame->cmd.payload[1] << 8 | frame->cmd.payload[2];
		}

	frame->cmd.crc = crc16_calc(frame->buffer,CMD_HDR_SIZE + frame->cmd.size);

	app_send_frame(frame);
}




void app_answer_frame(frame_t *frame)
{
	switch(frame->cmd.reg)
	{
	case CMD_ITF_VER:
		app_decode_and_answer_version(frame);
		break;

	case CMD_IDENT:
		app_decode_and_answer_ident(frame);// chama a funcao de identificacao dos pontos
		break;

	case CMD_POINT_DESC_BASE:
	case CMD_POINT_DESC_BASE+1:
	case CMD_POINT_DESC_BASE+2:
		app_decode_and_answer_desc(frame);
	//case CMD_POINT_DESC_BASE+n:
	// uint8_t p = frame->cmd.reg - CMD_POINT_DESC_BASE;
	break;

	case CMD_POINT_READ_BASE:
	case CMD_POINT_READ_BASE+1:
	case CMD_POINT_READ_BASE+2:
		app_decode_and_answer_read(frame);
	//case CMD_POINT_READ_BASE+n:
	// uint8_t p = frame->cmd.reg - CMD_POINT_READ_BASE;
	break;

	case CMD_POINT_WRITE_BASE:
	case CMD_POINT_WRITE_BASE+1:
	case CMD_POINT_WRITE_BASE+2:
		app_decode_and_answer_write(frame);
	//case CMD_POINT_WRITE_BASE+n:
	// uint8_t p = frame->cmd.reg - CMD_POINT_WRITE_BASE;
	break;

	default:
		break;
	}
}



void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
	//HAL_GPIO_TogglePin(GPIOA, LEDTESTE_Pin);
	if(htim==&htim2)
	{
		// A interrupção é chamada uma vez por milissegundo, procurando por quaisquer impulsos do sensor!
		 //Neste manipulador de interrupções, faremos todas as coisas que costumamos fazer no loop.

		GPIO_PinState x = HAL_GPIO_ReadPin(GPIOB, FLOWMETER_Pin);

		if (x == lastflowpinstate) {
			lastflowratetimer++;
			return; // nothing changed!
		}

		if (x == 1) {
			HAL_GPIO_TogglePin(GPIOA, LEDTESTE_Pin);
			//low to high transition!
			pulses++;
		}

		lastflowpinstate = x;
		flowrate = 1000.0;
		flowrate /= lastflowratetimer;  // em hertz
		lastflowratetimer = 0;
	}
	  liters = pulses;
	  liters = liters/7.5;
	  liters = liters/60.0;



}


void app_set_new_frame_state(bool state)
{
	app_new_frame = state;
}

bool app_get_new_frame_state(void)
{
	return app_new_frame;
}

void app_init(void)
{
	frame.cmd.rx_bytes = 0;
	app_set_new_frame_state(false);
	hw_rx_enable(true);
	hw_uart_init();

	lcd_init();
	lcd_send_cmd (0x01);  //limpa display
	HAL_Delay(500);
	lcd_send_cmd (0x80);
	lcd_send_string ("INICIALIZANDO...");
	HAL_Delay(3000);
	lcd_send_cmd (0x01);  //limpa display
	HAL_Delay(500);
	app_started = true;
}

static void write_lcd(void)
{
    	gcvt (liters,4, send_liters);

    	itoa(conta_litro, send_conta,10);

		lcd_send_cmd (0x80);
		lcd_send_string ("LITROS ATS.:     ");

		lcd_send_cmd (0x8B);
		lcd_send_string (send_liters);

		lcd_send_cmd (0xC0);
		lcd_send_string ("SET:     ");

		lcd_send_cmd (0xC4);
		lcd_send_string (send_conta);

}

void app_systick_cbk(void)
{
	static uint32_t lcd_updt = 0;

	if(!app_started)
		return;

	if(++lcd_updt >= 1000)
	{
		lcd_updt = 0;
		write_lcd();
	}
}

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
	if(GPIO_Pin == BTN_Pin)
	{

			if(HAL_GetTick() - debounce >250)
			{

				  conta_litro = conta_litro + 1;

				  debounce = HAL_GetTick();

			}

	}
	else if(GPIO_Pin == BTNDOWN_Pin)
		{

				if(HAL_GetTick() - debounce2 >250)
				{
				   conta_litro = conta_litro - 1;

				   debounce2 = HAL_GetTick();

				}


		}

	else if (GPIO_Pin == BTNSET_Pin)
	{
		{
			if(HAL_GetTick() - debounce3 >250)
			{
				HAL_GPIO_WritePin(GPIOB, RELE_Pin, GPIO_PIN_SET);
				Rele_ON = 1;
				debounce3 = HAL_GetTick();

			}
		}

	}

}

void app_loop(void)
{


	if (Rele_ON == true)
	{
		if (liters > conta_litro)
		{
			HAL_GPIO_WritePin(GPIOB, RELE_Pin, GPIO_PIN_RESET);
			pulses = 0;
			conta_litro = 0;
			send_conta[0]= 0;
			send_conta[1]= 0;
			send_conta[2]= 0;
			send_conta[3]= 0;
			send_conta[4]= 0;
			//Rele_ON = false;
		}
	}


	if(app_get_new_frame_state())
	{
		if(app_check_frame(&frame))
			app_answer_frame(&frame);

		app_set_new_frame_state(false);
		frame.cmd.rx_bytes = 0;
	}
}
