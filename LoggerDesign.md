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
- Also a possibility to upload the logs to a specific place
- Execute commands until receiving a exit cmd
