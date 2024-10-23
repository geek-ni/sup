#include <Servo.h>
#include <SPI.h>
#include <PN532_SPI.h>
#include <PN532.h>

const int servoPin = 8;   // Servo control pin
String inputString = "";  // Для получения команды через Serial
bool stringComplete = false;
Servo servo;

// NFC
PN532_SPI pn532spi(SPI, 10);
PN532 nfc(pn532spi);

bool servoMoving = false;
unsigned long lastNFCScan = 0;
const unsigned long NFCScanInterval = 500; // Интервал сканирования NFC

// Для асинхронного управления серво
unsigned long servoMoveStartTime = 0;
const unsigned long servoOpenDuration = 400;  // Время для открытия
const unsigned long doorOpenDuration = 5000;  // Задержка с открытой дверью
const unsigned long servoCloseDuration = 400; // Время для закрытия
int servoState = 0;  // Состояние серво (0 - покой, 1 - открытие, 2 - ожидание, 3 - закрытие)

void setup() {
  servo.attach(servoPin);
  servo.write(90);  // Серво в исходное положение
  Serial.begin(9600);
  inputString.reserve(200);
  Serial.println("Arduino ready");

  // Инициализация NFC
  nfc.begin();
  uint32_t versiondata = nfc.getFirmwareVersion();
  if (!versiondata) {
    Serial.println("Didn't find PN53x board");
    while (1); // Остановка если NFC не найден
  }
  nfc.SAMConfig();
  //Serial.println("Waiting for an NFC card...");
}

void loop() {
  // Обработка команд через Serial
  if (stringComplete) {
    processSerialCommand();  // Обрабатываем команду
    inputString = "";  // Очищаем строку
    stringComplete = false;  // Сбрасываем флаг
  }

  // Сканирование NFC с определенным интервалом
  if (millis() - lastNFCScan >= NFCScanInterval) {
    scanNFC();  // Сканируем NFC
    lastNFCScan = millis();
  }

  // Асинхронное управление серво
  manageServo();  // Управление серво
}

void serialEvent() {
  // Читаем данные из Serial без блокировки
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    inputString += inChar;
    if (inChar == '\n') {
      stringComplete = true;  // Команда полностью получена
    }
  }
}

void processSerialCommand() {
  inputString.trim();  // Убираем лишние пробелы и символы
  //Serial.print("Received command: ");
  Serial.println(inputString);

  // Открытие двери по команде
  if (inputString == "OpenDoor") {
    if (!servoMoving) {
      Serial.println("Executing OpenDoor command");
      startServoMovement();  // Начинаем движение серво
    }
  } else {
    //Serial.println("Unknown command");  // Если команда неизвестна
  }
}

void scanNFC() {
  uint8_t success;
  uint8_t uid[] = { 0, 0, 0, 0, 0, 0, 0 };
  uint8_t uidLength;

  success = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 50); // Таймаут 50ms

  if (success) {
    //Serial.println("Found an NFC card!");
    Serial.print("NFC: ");
    for (uint8_t i = 0; i < uidLength; i++) {
      Serial.print("0x");
      Serial.print(uid[i], HEX);
      Serial.print(" ");
    }
    delay(200);
    Serial.println("");
  } else {
    //Serial.println("No NFC card detected");  // Если карта не найдена
  }
}

void startServoMovement() {
  servoMoving = true;  // Устанавливаем флаг движения серво
  servoState = 1;  // Начинаем открытие двери
  servoMoveStartTime = millis();  // Засекаем время начала движения
}

void manageServo() {
  if (!servoMoving) return;  // Если серво не двигается, выходим

  unsigned long currentTime = millis();
  switch (servoState) {
    case 1: // Открытие двери
      if (currentTime - servoMoveStartTime < servoOpenDuration) {
        servo.write(180);  // Поворот для открытия
      } else {
        servo.write(90);   // Остановка серво
        servoState = 2;    // Ожидание с открытой дверью
        servoMoveStartTime = currentTime;
      }
      break;
    case 2: // Ожидание с открытой дверью
      if (currentTime - servoMoveStartTime >= doorOpenDuration) {
        servoState = 3;    // Переход к закрытию
        servoMoveStartTime = currentTime;
      }
      break;
    case 3: // Закрытие двери
      if (currentTime - servoMoveStartTime < servoCloseDuration) {
        servo.write(0);    // Поворот для закрытия
      } else {
        servo.write(90);   // Возвращаем серво в исходное положение
        servoState = 0;    // Сброс состояния
        servoMoving = false;  // Серво больше не двигается
        nfc.begin();  // Переинициализация NFC после движения серво
        nfc.SAMConfig();  // Настройка SAM снова
        Serial.println("NFC:reinitialized");  // Логирование переинициализации
        delay(200);
      }
      break;
  }
}
