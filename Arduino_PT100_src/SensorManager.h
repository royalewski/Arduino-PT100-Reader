#pragma once
#include <Arduino.h>
#include "Sensors.h"

struct Slot {
  bool        isUsed;  
  SensorPT100 s;

  Slot() : isUsed(false), s() {}
};

class SensorManager {
public:
  static const uint8_t MAX_SENSORS = 8;
  Slot slots[MAX_SENSORS];

  SensorManager(); 

  SensorPT100* findById(uint8_t id);
  bool exists(uint8_t id);
  bool isActive(uint8_t id);
  bool create(bool active, uint8_t id, uint8_t pin, const String& name,
              float t1 = 0.0f, int q1 = 0, float t2 = 100.0f, int q2 = 1023, uint32_t interval = 0);
  bool remove(uint8_t id);
  void forEach(void (*fn)(SensorPT100&));
};
