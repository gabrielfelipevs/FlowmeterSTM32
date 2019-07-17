/*
 * hw.c
 *
 *  Created on: 15 de abr de 2019
 *      Author: Marcelo
 */

#include <stdint.h>
#include <stdbool.h>
#include "main.h"
#include "cmd.h"
#include "app.h"
#include "hw.h"

extern UART_HandleTypeDef huart2;
#define USART_PORT        huart2.Instance
#define USART_IRQ         USART2_IRQn
#define USART_IRQ_PRIO    1

void hw_usart_irq_handler(UART_HandleTypeDef *huart)
{
	uint8_t c;
	uint8_t v = 0;
	uint32_t sr;

	sr = USART_PORT->SR;
	while(sr & (UART_FLAG_ORE | UART_FLAG_PE | UART_FLAG_FE | UART_FLAG_NE))
	{
		sr = USART_PORT->SR;
		c = USART_PORT->DR;
	}

	if(sr & UART_FLAG_RXNE)
	{
		c = USART_PORT->DR;
		v = 1;
	}

	if(v)
	{
		if(app_get_new_frame_state() == false)
		{
			if(app_add_received_byte(c))
				app_set_new_frame_state(true);
		}
	}
}

void hw_uart_send_byte(uint8_t c, uint8_t with_esc)
{
	while( !(USART_PORT->SR & UART_FLAG_TXE)) {}

	if(with_esc)
	{
		if(c == FRAME_FLAG || c == FRAME_ESC)
		{
			USART_PORT->DR = FRAME_ESC;
			while( !(USART_PORT->SR & UART_FLAG_TXE)) {}
		}
	}

	USART_PORT->DR = c;
}

void hw_rx_enable (bool enable)
{
	if (enable)
	{
		// LOW = RX
		HAL_GPIO_WritePin(nRE_GPIO_Port,nRE_Pin,GPIO_PIN_RESET);
		HAL_GPIO_WritePin(DE_GPIO_Port,DE_Pin,GPIO_PIN_RESET);
	}
	else
	{
		// HIGH = TX
		HAL_GPIO_WritePin(nRE_GPIO_Port,nRE_Pin,GPIO_PIN_SET);
		HAL_GPIO_WritePin(DE_GPIO_Port,DE_Pin,GPIO_PIN_SET);
	}
}

void hw_delay(uint32_t t_ms)
{
	HAL_Delay(t_ms);
}

void hw_uart_init(void)
{
	// enabling interrupts for errors
	//   (Frame error, noise error, overrun error)
	USART_PORT->CR3 |= USART_CR3_EIE;
	// enabling interrupt for parity errors and rx
	USART_PORT->CR1 |= USART_CR1_PEIE | USART_CR1_RXNEIE;

	HAL_NVIC_SetPriority(USART_IRQ, USART_IRQ_PRIO, 0);
	HAL_NVIC_EnableIRQ(USART_IRQ);
	HAL_NVIC_ClearPendingIRQ(USART_IRQ);
}
