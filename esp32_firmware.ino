#include <WiFi.h>
#include <HTTPClient.h>

// === WIFI CONFIGURATION ===
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// === SERVER CONFIGURATION ===
// Replace with the IPv4 address of your computer running the Flask app
// Example: http://192.168.1.5:5000/iot_update
const char* serverUrl = "http://YOUR_LOCAL_IP:5000/iot_update";

// === HOTSPOT LOCATION ===
// This describes where this specific ESP32 is placed.
const char* hotspotLocation = "CollegeGate";

void setup() {
  Serial.begin(115200);
  
  // 1. Connect to WiFi network
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println();
  Serial.println("Connected to WiFi successfully!");
  Serial.print("ESP32 IP Address: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  // === BLUETOOTH BEACON SIMULATION ===
  // In your full hardware build, the ESP32 would use BLE (Bluetooth Low Energy)
  // to constantly scan the room. When it detects a specific MAC address matching 
  // 'PERSON_001', it will trigger the HTTP request below.
  
  // For software validation, we simulate finding the beacon every 60 seconds.
  String detectedDevice = "PERSON_001";
  
  Serial.println("----------------------------------------");
  Serial.print("Detected Missing Person Beacon: ");
  Serial.println(detectedDevice);
  
  // Send the HTTP GET request to the Flask server
  sendLocationUpdate(detectedDevice, hotspotLocation);
  
  // Wait 60 seconds before scanning again
  delay(60000); 
}

void sendLocationUpdate(String device_id, String location) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    
    // Format: http://192.168.x.x:5000/iot_update?device_id=PERSON_001&location=CollegeGate
    String queryUrl = String(serverUrl) + "?device_id=" + device_id + "&location=" + location;
    
    Serial.print("Sending alert to server: ");
    Serial.println(queryUrl);
    
    http.begin(queryUrl);
    
    // Perform the GET request
    int httpResponseCode = http.GET();
    
    if (httpResponseCode > 0) {
      Serial.print("Server Response Code: ");
      Serial.println(httpResponseCode);
      String payload = http.getString();
      Serial.println("Server Message: " + payload);
    } else {
      Serial.print("HTTP Connection Error: ");
      Serial.println(httpResponseCode);
      Serial.println("Make sure your Flask server is running and the IP address is correct.");
    }
    
    http.end(); // Free memory
  } else {
    Serial.println("WiFi Connection Lost!");
  }
}
