#include "LineHandler.h"
#include "SensorManager.h"  


const uint8_t MAX_Name = 21;   
static char LH_buf[LH_buf_size];
static size_t LH_len = 0;

static int parseAnalogPin(const char* s){
    if (s[0] == 'A' || s[0]=='a')
        return A0 + atoi(s+1);
    return atoi(s);
}

static bool g_listFirst = true;

static void printSensorItem(SensorPT100& s) {
  if (!g_listFirst) Serial.print(',');
  g_listFirst = false;

  Serial.print(F("{\"id\":"));     Serial.print(s.ID);
  Serial.print(F(",\"name\":\"")); Serial.print(s.NAME);
  Serial.print(F("\",\"pin\":"));  Serial.print(s.PIN);
  Serial.print(F(",\"active\":")); Serial.print(s.Active ? 1 : 0);
  Serial.print('}');
}

static bool parseKeyVal (char* tok, char*& k,  char*& v){
    k = tok;
    char* eq = strchr(tok, '=');
    if (!eq) return false;
    *eq = '\0';
    v = eq + 1;
    return true;
}

static void handleLine(char* line, SensorManager& mgr){
    for (char* p=line; *p; ++p)
        if (*p == '\r')
            *p = '\0';

    char* saveptr = nullptr;
    char* cmd = strtok_r(line, " \t", &saveptr);
    if (!cmd) return;

    auto eq = [](const char* a, const char* b){ return strcasecmp(a,b)==0; };

    if (eq(cmd, "NEW")) {
      int id = -1, pin = -1, q1 = 0, q2 = 1023, interval = 0;
      bool active = false, haveID = false, havePIN = false, haveNAME = false;
      char name[MAX_Name] = {0};
      float t1 = 0.0f, t2 = 100.0f;

      for (char* tok = strtok_r(nullptr, " \t", &saveptr);
           tok;
           tok = strtok_r(nullptr, " \t", &saveptr))
      {
          char *k, *v;
          if (!parseKeyVal(tok, k, v)) continue;

          if      (eq(k, "id"))      { id = atoi(v); haveID = true; }
          else if (eq(k, "active"))  { active = atoi(v) != 0; }
          else if (eq(k, "pin"))     { pin = parseAnalogPin(v); havePIN = true; }
          else if (eq(k, "name"))    { strncpy(name, v, MAX_Name - 1); haveNAME = true; }
          else if (eq(k, "t1"))      { t1 = atof(v); }
          else if (eq(k, "q1"))      { q1 = atoi(v); }
          else if (eq(k, "t2"))      { t2 = atof(v); }
          else if (eq(k, "q2"))      { q2 = atoi(v); }
          else if (eq(k,"interval")) { interval = (uint32_t)atoi(v); }

      }

      if (!haveID || !havePIN) { Serial.println(F("{\"ok\":false,\"err\":\"need id&pin\"}")); return; }
      if (!haveNAME) strncpy(name, "PT100", MAX_Name - 1);
      if (q1 == q2) q2 = q1 + 1;
      bool ok = mgr.create(
          active,
          (uint8_t)id,
          (uint8_t)pin,
          String(name),
          t1,   // T1
          q1,   // Q1
          t2,   // T2
          q2,    // Q2
          interval
      );
      Serial.println(ok ? F("{\"ok\":true}") : F("{\"ok\":false,\"err\":\"exists_or_full\"}"));
    }

    else if (eq(cmd,"DEL")) {
      int id=-1;
      for (char* tok=strtok_r(nullptr," \t",&saveptr); tok; tok=strtok_r(nullptr," \t",&saveptr)) {
        char *k,*v; if (!parseKeyVal(tok,k,v)) continue;
        if (eq(k,"id")) id=atoi(v);
      }
      bool ok = (id>=0) && mgr.remove((uint8_t)id);
      Serial.println(ok ? F("{\"ok\":true}") : F("{\"ok\":false,\"err\":\"no_such_id\"}"));
    }

    else if (eq(cmd,"SET")) {
      int id = -1;

      bool hasActive=false; bool newActive=false;
      bool hasPin=false;     int  newPin=-1;
      bool hasName=false;    char newName[MAX_Name] = {0};
      bool hasT1=false;      float newT1=0.0f;
      bool hasQ1=false;      int   newQ1=0;
      bool hasT2=false;      float newT2=0.0f;
      bool hasQ2=false;      int   newQ2=0;
      bool hasInterval=false;uint32_t newInterval=0;

      for (char* tok=strtok_r(nullptr," \t",&saveptr);
          tok;
          tok=strtok_r(nullptr," \t",&saveptr))
      {
        char *k,*v; if (!parseKeyVal(tok,k,v)) continue;

        if      (eq(k,"id"))       { id = atoi(v); }
        else if (eq(k,"active"))   { hasActive=true;   newActive = atoi(v)!=0; }
        else if (eq(k,"pin"))      { hasPin=true;      newPin = parseAnalogPin(v); }
        else if (eq(k,"name"))     { hasName=true;     strncpy(newName, v, MAX_Name-1); }
        else if (eq(k,"t1"))       { hasT1=true;       newT1 = atof(v); }
        else if (eq(k,"q1"))       { hasQ1=true;       newQ1 = atoi(v); }
        else if (eq(k,"t2"))       { hasT2=true;       newT2 = atof(v); }
        else if (eq(k,"q2"))       { hasQ2=true;       newQ2 = atoi(v); }
        else if (eq(k,"interval")) { hasInterval=true; newInterval = (uint32_t)strtoul(v, nullptr, 10); }
      }

      auto s = mgr.findById((uint8_t)id);
      if (!s) { Serial.println(F("{\"ok\":false,\"err\":\"no_such_id\"}")); return; }

      if (hasActive)  s->Active = newActive;
      if (hasPin && newPin>=0) s->PIN = (uint8_t)newPin;
      if (hasName)    s->NAME = String(newName);
      if (hasT1)      s->T1 = newT1;
      if (hasQ1)      s->Q1 = newQ1;
      if (hasT2)      s->T2 = newT2;
      if (hasQ2)      s->Q2 = newQ2;
      if (s->Q1==s->Q2) s->Q2 = s->Q1 + 1;

      if (hasInterval) {
        s->ReportInterval = newInterval;
        s->LastReport = newInterval ? (uint32_t)(millis() - newInterval) : millis();
      }

      Serial.println(F("{\"ok\":true}"));
  }


    else if (eq(cmd,"READ")) {
      int id=-1;
      for (char* tok=strtok_r(nullptr," \t",&saveptr); tok; tok=strtok_r(nullptr," \t",&saveptr)) {
        char *k,*v; if (!parseKeyVal(tok,k,v)) continue;
        if (eq(k,"id")) id=atoi(v);
      }
      auto s = mgr.findById((uint8_t)id); 
      if (!s) { Serial.println(F("{\"ok\":false,\"err\":\"no_such_id\"}")); return; }

      float t = s->ReadTemp();
      Serial.print(F("{\"ok\":true,\"id\":"));   Serial.print(s->ID);
      Serial.print(F(",\"name\":\""));           Serial.print(s->NAME);
      Serial.print(F("\",\"t\":"));              Serial.print(t,2);
      Serial.println(F("}"));
    }

    else if (eq(cmd,"LIST")) {
      Serial.print(F("{\"s\":["));
      g_listFirst = true;
      mgr.forEach(printSensorItem);
      Serial.println(F("]}"));
    }
    
    else {
      Serial.println(F("{\"ok\":false,\"err\":\"unknown_cmd\"}"));
    }
}

void LineHandler_tick(SensorManager& mgr) {
  while (Serial.available()) {
    const char c = (char)Serial.read();
    if (c=='\n' || c=='\r') {
      if (LH_len > 0) {
        LH_buf[LH_len] = '\0';
        handleLine(LH_buf, mgr);
        LH_len = 0;
      }
    } else {
      if (LH_len < sizeof(LH_buf)-1) {
        LH_buf[LH_len++] = c;
      } else {
        LH_len = 0;
        Serial.println(F("{\"ok\":false,\"err\":\"line_overflow\"}"));
      }
    }
  }
}
