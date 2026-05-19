#pragma once
#include <Arduino.h>

class SensorPT100 {
public:
  bool Active;  
  uint8_t ID;
  uint8_t PIN;
  String  NAME;
  // 2-point calibration: T = T1 + (ADC - Q1) * (T2 - T1) / (Q2 - Q1)
  float   T1, T2;
  int     Q1, Q2;  
  float   LastTemp; 
  uint32_t ReportInterval;  
  uint32_t LastReport; 
  SensorPT100(); //Default constructor - creating a sensor without any parameters
  SensorPT100(bool active, uint8_t id, uint8_t pin,
              const String& name = ""); // Creating a sensor with incomplete parameters
  // opcjonalnie pełny z kalibracją:
  SensorPT100(bool active, uint8_t id, uint8_t pin,
              const String& name, float t1, int q1, float t2, int q2); // Setting every parameter during sensor creation

  void SetValues(bool active, uint8_t id, uint8_t pin, const String& name,
                 float t1, int q1, float t2, int q2); // Setting parameters after sensor creation

  float ReadTemp();       //Reading temeperature
  void  SendTempUSART();  //Sending temperature through USART
  void  reset();          //Zeroing parameters
  bool shouldReport();    //Checking if a sensor should report temperature, due to interval
};
