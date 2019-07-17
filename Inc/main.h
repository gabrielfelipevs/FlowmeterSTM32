/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Header for main.c file.
  *                   This file contains the common defines of the application.
  ******************************************************************************
  * @attention
  *
  * <h2><center>&copy; Copyright (c) 2019 STMicroelectronics.
  * All rights reserved.</center></h2>
  *
  * This software component is licensed by ST under BSD 3-Clause license,
  * the "License"; You may not use this file except in compliance with the
  * License. You may obtain a copy of the License at:
  *                        opensource.org/licenses/BSD-3-Clause
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32f1xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */

/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */

/* USER CODE END EM */

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */

/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
#define LED_Pin GPIO_PIN_13
#define LED_GPIO_Port GPIOC
#define SW_Pin GPIO_PIN_0
#define SW_GPIO_Port GPIOA
#define DE_Pin GPIO_PIN_4
#define DE_GPIO_Port GPIOA
#define nRE_Pin GPIO_PIN_5
#define nRE_GPIO_Port GPIOA
#define BTN_Pin GPIO_PIN_0
#define BTN_GPIO_Port GPIOB
#define BTN_EXTI_IRQn EXTI0_IRQn
#define RELE_Pin GPIO_PIN_10
#define RELE_GPIO_Port GPIOB
#define BTNSET_Pin GPIO_PIN_11
#define BTNSET_GPIO_Port GPIOB
#define BTNSET_EXTI_IRQn EXTI15_10_IRQn
#define FLOWMETER_Pin GPIO_PIN_12
#define FLOWMETER_GPIO_Port GPIOB
#define LEDTESTE_Pin GPIO_PIN_10
#define LEDTESTE_GPIO_Port GPIOA
#define BTNDOWN_Pin GPIO_PIN_7
#define BTNDOWN_GPIO_Port GPIOB
#define BTNDOWN_EXTI_IRQn EXTI9_5_IRQn
/* USER CODE BEGIN Private defines */

/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */

/************************ (C) COPYRIGHT STMicroelectronics *****END OF FILE****/
