#include "Sensors.h"


SensorPT100::SensorPT100()
  : Active(false),
    ID(0), PIN(A0), NAME(""),
    T1(0.0f), T2(100.0f), 
    Q1(0),   Q2(1023),   
    LastTemp(NAN),
    ReportInterval(0), LastReport(0) {}

SensorPT100::SensorPT100(bool active, uint8_t id, uint8_t pin, const String& name)
  : Active(active),
    ID(id), PIN(pin), NAME(name),
    T1(0.0f), T2(100.0f),
    Q1(0),   Q2(1023),
    LastTemp(NAN) {}

SensorPT100::SensorPT100(bool active, uint8_t id, uint8_t pin, const String& name,
                         float t1, int q1, float t2, int q2)
  : Active(active),
    ID(id), PIN(pin), NAME(name),
    T1(t1), T2(t2), Q1(q1), Q2(q2),
    LastTemp(NAN)
{
  if (Q1 == Q2) Q2 = Q1 + 1; // Avoid dividing by 0
}

// --- Ustawienia ---

void SensorPT100::SetValues(bool active, uint8_t id, uint8_t pin, const String& name,
                            float t1, int q1, float t2, int q2)
{
  Active = active; ID = id; PIN = pin; NAME = name;
  T1 = t1; Q1 = q1; T2 = t2; Q2 = q2;
  if (Q1 == Q2) Q2 = Q1 + 1;
}

float SensorPT100::ReadTemp() {
  // 1) uśrednij ADC
  const int n = 63;
  long s = 0;
  for (int i = 0; i < n; ++i)
    s += analogRead(PIN);
  const int adc = (int)(s / n);

  //T = T1 + (ADC - Q1) * (T2 - T1) / (Q2 - Q1)
  const long dQ = (long)Q2 - (long)Q1;
  const float dT = T2 - T1;
  float T = T1 + ((float)(adc - Q1) * dT) / (float)dQ;

  LastTemp = T;
  return T;
}

void SensorPT100::SendTempUSART() {
  if (isnan(LastTemp)) {
    ReadTemp();
  }
  Serial.print(F("ID="));       Serial.print(ID);
  Serial.print(F(" NAME="));    Serial.print(NAME);
  Serial.print(F(" Temperature=")); Serial.print(LastTemp, 2);
  Serial.println(F(" C"));
}

void SensorPT100::reset() {
  *this = SensorPT100(); 
}

bool SensorPT100::shouldReport() {
  if (!Active || ReportInterval == 0) 
    return false;
  uint32_t now = millis();
  if (now - LastReport >= ReportInterval) {
    LastReport = now;
    return true;
  }
  return false;
}