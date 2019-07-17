/*
 * app.h
 *
 *  Created on: 15 de abr de 2019
 *      Author: Marcelo
 */

#ifndef APP_H_
#define APP_H_

void app_init(void);
void app_loop(void);
void app_set_new_frame_state(bool state);
bool app_get_new_frame_state(void);
bool app_add_received_byte(uint8_t b);

#endif /* APP_H_ */
