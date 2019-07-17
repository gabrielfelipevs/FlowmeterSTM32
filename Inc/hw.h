/*
 * hw.h
 *
 *  Created on: 15 de abr de 2019
 *      Author: Marcelo
 */

#ifndef HW_H_
#define HW_H_

void hw_uart_send_byte(uint8_t c, uint8_t with_esc);
void hw_uart_init(void);
void hw_delay(uint32_t t_ms);
void hw_rx_enable (bool enable);

#endif /* HW_H_ */
