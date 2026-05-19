#pragma once
#include <Arduino.h>

class SensorManager;

void LineHandler_tick(SensorManager& mgr);

#ifndef LH_BAUD
#define LH_BAUD 9600
#endif

#ifndef LH_buf_size
#define LH_buf_size 160
#endif
