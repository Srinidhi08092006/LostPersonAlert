#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>

// ==========================================
// 1. YOUR CONFIGURATION
// ==========================================
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// REPLACE THIS with your computer's IP address where Flask is running
const char* serverUrl = "http://YOUR_LOCAL_IP:5000/iot_update";

// ==========================================
// 2. HARDWARE PINS
// ==========================================
// The ESP8266 NodeMCU has a built-in "FLASH" button connected to GPIO 0
const int BUTTON_PIN = 0; 

// The ESP8266 NodeMCU has a built-in blue LED connected to GPIO 2
const int LED_PIN = 2;    

WiFiClient client;

void setup() {
  Serial.begin(115200);
  
  // Setup the button as an input 
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  // Setup the LED as an output (Note: Built-in LED is usually active LOW)
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH); // Turn off LED at start
  
  Serial.println();
  Serial.println("-----------------------------------");
  Serial.println("LOST PERSON ALERT IOT SCANNER READY");
  Serial.println("-----------------------------------");
  
  // Connect to WiFi network
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\nWiFi Connected!");
  Serial.print("Board IP Address: ");
  Serial.println(WiFi.localIP());
  Serial.println("-----------------------------------");
  Serial.println("Press the 'FLASH' button on the board to simulate detecting a person.");
}

void loop() {
  // Read the state of the built-in FLASH button. 
  // It reads LOW when you are pressing it down.
  int buttonState = digitalRead(BUTTON_PIN);
  
  if (buttonState == LOW) {
    Serial.println("\n[ALERT] Hardware sensor triggered! Person Detected.");
    
    // Turn ON the built-in blue LED to show it's transmitting
    digitalWrite(LED_PIN, LOW); 
    
    // Send the alert to your Flask server
    sendLocationUpdate("PERSON_001", "MainGate_Scanner");
    
    // Wait for you to let go of the button so it doesn't spam the server
    while(digitalRead(BUTTON_PIN) == LOW) {
      delay(50);
    }
    
    // Turn OFF the LED after transmission
    digitalWrite(LED_PIN, HIGH); 
    
    // 1 second cooldown
    delay(1000); 
  }
}

void sendLocationUpdate(String device_id, String location) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    
    // Build the URL to hit the Flask route
    String queryUrl = String(serverUrl) + "?device_id=" + device_id + "&location=" + location;
    
    Serial.print("Sending Data to Server: ");
    Serial.println(queryUrl);
    
    http.begin(client, queryUrl);
    
    // Perform the HTTP GET request
    int httpResponseCode = http.GET();
    
    if (httpResponseCode > 0) {
      Serial.print("Server Response Code: ");
      Serial.println(httpResponseCode); // 200 means success!
      String payload = http.getString();
      Serial.println("Server Message: " + payload);
    } else {
      Serial.print("Connection Error. Code: ");
      Serial.println(httpResponseCode);
      Serial.println("Check if Flask is running and the IP is correct.");
    }
    
    http.end(); // Free memory
  } else {
    Serial.println("WiFi Disconnected!");
  }
}
