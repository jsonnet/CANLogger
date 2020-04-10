## CAN Logger Design Idea

### Init Phase
- Init GPS / GSM connections
- Init CAN controllers to 500 kbps and open filter
- Check online for new software update (OTA - GitHub)
- Init Telegram Bot

### Logging Phase
- Log incoming CAN messages with timestamp (unix) and ID in log file
- If filter is set only log for specified can ids
- Log periodically GPS position data with timestamp to match
- Log accelerometer data 
- Check for attack flag set by GSM Modul upon a call interrupt
- If no new CAN messages arrive wait for timeout and set soft sleep

### Attack Phase
- Check Telegram for new command and execute
- Replay attack (parameter with id)
- Injection attack (parameter with id to send from and payload)
- Bus-Off attack for specific modules
- Set filter for specific CAN ids during logging
- Download log file via Telegram
- Wait and execute commands until receiving a exit cmd


## Execution Plan
- OTA update by checking the current installed version against the one online (GET request to GitHub for latest version), if newer one is found override main file and do soft restart
- The attack phase should get initiated with a call to the GSM module, as it features a RING pin which goes HIGH when receiving a call. Thus we can use an interrupt which features a flag that gets set. During this phase the board will check Telegram for new commands to be executed.
- Also we should monitor when the car is shutoff (so no more messages for a specific time) as we are connected to constant power. Thus when turned off, we put the GSM and GPS as well as the board to sleep. The board will also be in soft sleep and wake up every few seconds to check for new messages else it will go to sleep again (reduces board power consumption to ~500 uA)
- The GPS module keeps track of satellites and position by itself but it is necessary to periodically request the data and log it (also logging once  every couple seconds should be way enough and reduces overhead)


## TODOs
- [ ] SD Card needs to be bought
