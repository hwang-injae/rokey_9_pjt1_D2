string step            # IDLE PICK WEIGH SHAKE SEAT SOAP WIPE RINSE RACK ISOLATE DONE ERROR PAUSED
string kind            # BOWL / CUP / ""
string zone_id         # 현재 반납 구역
uint16 done_bowl
uint16 done_cup
uint16 isolated
uint16 target_bowl     # 계획 수량 (진행률)
uint16 target_cup
uint16 sponge_uses
uint16 soap_dips
uint16 rinse_dips
string last_code
string message
builtin_interfaces/Time stamp
