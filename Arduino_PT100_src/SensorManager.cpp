#include "SensorManager.h"

SensorManager::SensorManager() {
  for (uint8_t i = 0; i < MAX_SENSORS; ++i) {
    slots[i].isUsed = false;
    slots[i].s.reset();
  }
}

SensorPT100* SensorManager::findById(uint8_t id) {
  for (uint8_t i = 0; i < MAX_SENSORS; ++i)
    if (slots[i].isUsed && slots[i].s.ID == id) return &slots[i].s;
  return nullptr;
}

bool SensorManager::exists(uint8_t id) {
  return findById(id) != nullptr;
}

bool SensorManager::isActive(uint8_t id) {
  SensorPT100* s = findById(id);
  return s && s->Active;
}

bool SensorManager::create(bool active, uint8_t id, uint8_t pin, const String& name,
                           float t1, int q1, float t2, int q2, uint32_t interval)
{
  if (exists(id)) 
    return false; 
  for (uint8_t i = 0; i < MAX_SENSORS; ++i) {
    if (!slots[i].isUsed) {
      slots[i].isUsed = true;
      slots[i].s = SensorPT100(active, id, pin, name);
      slots[i].s.T1 = t1;  slots[i].s.Q1 = q1;
      slots[i].s.T2 = t2;  slots[i].s.Q2 = q2;
      slots[i].s.ReportInterval = interval;
      if (slots[i].s.Q1 == slots[i].s.Q2) slots[i].s.Q2 = slots[i].s.Q1 + 1;
      return true;
    }
  }
  return false;
}

bool SensorManager::remove(uint8_t id) {
  for (uint8_t i = 0; i < MAX_SENSORS; ++i) {
    if (slots[i].isUsed && slots[i].s.ID == id) {
      slots[i].isUsed = false;
      slots[i].s.reset();
      return true;
    }
  }
  return false;
}

void SensorManager::forEach(void (*fn)(SensorPT100&)) {
  for (uint8_t i = 0; i < MAX_SENSORS; ++i)
    if (slots[i].isUsed) fn(slots[i].s);
}
