##CAN Logger Design Idea

###Init Phase
- Init GPS / GSM connections
- Check online for new software update (OTA - GitHub)

###Logging Phase
- Log incoming CAN messages with timestamp (unix) and ID in log file
- Log periodically GPS position data with timestamp to match
- Log accelerometer data 
- Check for attack flag

###Attack Phase
- Check online web hook for commands and execute
- Replay attack (parameter with id)
- Ingestion attack (parameter with id to send from and payload)
- Bus-Off attack for specific modules
- Also a possibility to upload the logs to a specific place
- Execute commands until receiving a exit cmd



##Execution Plan
- OTA update by checking the current installed version against the one online (GET request to GitHub for latest version), if newer one is found override main file and do soft restart
- The attack phase should get initiated with a call to the GSM module, as it features a RING pin which goes HIGH when receiving a call. Thus we can use an interrupt which features a flag that gets set (also the call should be ended and possibly a conformation GitHubSMS is send)
- Also we should monitor when the car is shutoff (so no more messages for a specific time) as we are connected to constant power. Thus when turned off, we put the GSM and GPS as well as the board to sleep. (The SN65HVD230 should have a feature to interrupt when new messages are received so to turn on the board and everything again)
- The GPS module keeps track of satellites and position by itself but it is necessary to periodically request the data and log it (also logging once  every couple seconds should be way enough and reduces overhead)


##TODOs
- [ ] still the CAN transceiver is not working as expected (or at all)
- [ ] SIM800L still good? Also needs SIM from ThingsMobile!
- [ ] SD Card needs to be bought
- [ ] Code implementation