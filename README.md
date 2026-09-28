# Felicity Battery (Local) — Home Assistant custom integration

Локальный (без облака) опрос батареи Felicity через её встроенный WiFi-модуль
по TCP-порту 53970 — тот же протокол, что использует приложение Shine в
локальном режиме и Node-RED-флоу с форумов.

## Важная оговорка

Точной официальной документации по протоколу нет. Карта полей собрана по
рабочему примеру для батареи Felicity 12.5 кВт·ч той же серии (LUX-E/LPBF).
LUX-E-48250LG03 тоже 12.5 кВт·ч — с высокой вероятностью протокол совпадает,
но 100% гарантии нет. Если какой-то сенсор показывает "unavailable" —
пришли сырой JSON-ответ (см. ниже), поправим ключи.

## Установка

1. Скопируй папку `custom_components/felicity_battery_local` в
   `<config>/custom_components/` твоей Home Assistant.
2. Перезапусти Home Assistant.
3. Settings → Devices & Services → Add Integration → "Felicity Battery (Local)".
4. Укажи IP батареи и порт (по умолчанию 53970).

Если при добавлении будет ошибка "не похоже на данные батареи" — значит
протокол/ключи отличаются, нужен сырой дамп для подгонки.

## Проверка вручную (перед установкой или для отладки)

```bash
python3 -c "
import socket
s = socket.create_connection(('IP_БАТАРЕИ', 53970), timeout=5)
s.sendall(b'wifilocalMonitor:get dev real infor')
s.settimeout(2)
data = b''
try:
    while True:
        chunk = s.recv(4096)
        if not chunk: break
        data += chunk
except socket.timeout:
    pass
print(data.decode(errors='ignore'))
"
```

## Какие сенсоры создаются

- State of Charge (%)
- State of Health (%) — если поле присутствует
- Battery Voltage / Current / Power
- Battery Temperature
- Battery State (full / standby / charging / discharging)
- Max / Min Cell Voltage, Cell Voltage Drift
- Max Charge / Discharge Current (лимиты BMS)
- Cell N Voltage — по одному сенсору на каждую ячейку (количество определяется
  автоматически при первом опросе)

## Источники

- Протокол и часть ключей: обсуждение на форуме simon42
  (Felicity Solar per API abfragen).
- Существующая cloud-интеграция для контекста:
  github.com/matheustavarestrindade/felicity_solar_hacs (работает через
  логин в shine.felicitysolar.com, к этому проекту не относится).
