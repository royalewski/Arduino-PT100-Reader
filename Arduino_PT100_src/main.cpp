
#include <Arduino.h>
#include "SensorManager.h" 
#include "LineHandler.h"     

#ifndef LH_BAUD
#define LH_BAUD 9600
#endif

SensorManager mgr;

void setup() {
  Serial.begin(LH_BAUD);
  Serial.println(F("{\"hello\":\"ready\"}"));
}

void loop() {
  LineHandler_tick(mgr);

  mgr.forEach([](SensorPT100& s) {
    if (s.shouldReport()) {
      float t = s.ReadTemp();
      Serial.print("Interval: "); Serial.println(s.ReportInterval);
      Serial.print(F("{\"id\":"));    Serial.print(s.ID);
      Serial.print(F(",\"name\":\"")); Serial.print(s.NAME);
      Serial.print(F("\",\"t\":"));    Serial.print(t,2);
      Serial.println(F("}"));
    }
  });

}
