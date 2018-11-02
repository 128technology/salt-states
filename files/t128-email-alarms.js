#!/usr/bin/env node

const EventSource = require('eventsource')
const NodeMailer = require('nodemailer')
var config = require('./config.js');

class T128Alarm {
  constructor(alarmData, subType){
    this.id = alarmData.id;
    this.node = alarmData.node;
    this.router = alarmData.router;
    this.process = alarmData.process;
    this.source = alarmData.source;
    this.number = alarmData.number;
    this.message = alarmData.message;
    this.category = alarmData.category;
    this.severity = alarmData.severity;
    this.shelvedStatus = alarmData.shelvedStatus;
    this.shelvedReason = alarmData.shelvedReason;
    this.value = alarmData.value;
    this.subType = subType;
  }
}

var alarmArray = new Array();

// set up event channel
var eventUrl = `https://${config.t128Address}/api/v1/events?token=${config.authToken}`
var eventSourceInitDict = {https: {rejectUnauthorized: false}}
var es = new EventSource(eventUrl, eventSourceInitDict)

// set up email
let poolConfig = {
  pool: true,
  host: config.mailHost,
  port: config.mailPort,
  secure: config.mailSecure,
  tls: {
    rejectUnauthorized: false
  }
}

if ( typeof config.mailUser !== 'undefined' && typeof config.mailPass !== 'undefined') {
  let auth = {
    user: config.mailUser,
    pass: config.mailPass
  };
  poolConfig['auth'] = auth
}

let transporter = NodeMailer.createTransport(poolConfig)
transporter.verify(function(error, success) {
   if (error) {
        console.log(error);
   } else {
        console.log('Server is ready to take our messages');
   }
});

// function to email any pending alarms every interval
function emailAlarms() {
  if (alarmArray.length > 0) {
    emailText = "";
    emailHTML = "<style>\n" +
                "table, th, td { border: 1px solid black; }\n" +
                ".CRITICAL { background-color: red; }\n" +
                ".MAJOR { background-color: orange; }\n" +
                ".MINOR { background-color: yellow; }\n" +
                ".ADD { background-color: Crimson; }\n" +
                ".CLEAR { background-color: CornflowerBlue; }\n" +
                "</style>";
    var intervalAlarms = {};
    alarmArray.forEach(function(value){
      if (value.subType === "ADD") {
        intervalAlarms[value.id] = value;
      } else if (value.subType === "CLEAR") {
        if (Object.keys(intervalAlarms).includes(value.id)) {
          // This alarm is already in the current interval Array, so let's pop it
          delete intervalAlarms[value.id];
        } else {
          // This is a clear from a previous interval, we should add it so a notification of the clear is sent
          intervalAlarms[value.id] = value;
        }
      }
    });
    //This switch supports three options:
    // ALWAYS_SEND_ALL - we want to always send all alarms/clears
    // SEND_CLEAR_INTERVAL - only send an email if all alarms did not clear, but send all alarms/clears during
    //                       the interval when this happens
    // NO_CLEAR_INTERVAL - only send an email if all alarms did not clear, only send the alarms that
    //                          did not clear
    switch(config.sendBehaviorEnum) {
      case 'ALWAYS_SEND_ALL':
      case 'SEND_CLEAR_INTERVAL':
        alarmArray.forEach(function(value){
          //emailText += "Alarm ID: " + value.id + "\n" +
          emailText +=  "Type: " + value.subType + "\n" +
                        "Severity: " + value.severity + "\n" +
                        "Router: " + value.router + "\n" +
                        "Node: " + value.node + "\n" +
                        "Category: " + value.category + "\n" +
                        "Message: " + value.message + "\n" +
                        "Source: " + value.source + "\n\n";

          emailHTML += "<table>\n" +
                       "<tr class=" + value.subType + "><td>Type:</td><td>" + value.subType + "</td></tr>\n" +
                       "<tr class=" + value.severity + "><td>Severity:</td><td>" + value.severity + "</td></tr>\n" +
                       "<tr><td>Router:</td><td>" + value.router + "</td></tr>\n" +
                       "<tr><td>Node:</td><td>" + value.node + "</td></tr>\n" +
                       "<tr><td>Category:</td><td>" + value.category + "</td></tr>\n" +
                       "<tr><td>Message:</td><td>" + value.message + "</td></tr>\n" +
                       "<tr><td>Source:</td><td>" + value.source + "</td></tr>\n<br>\n";
        });
        break;
      case 'NO_CLEAR_INTERVAL':
        for (var alarm in intervalAlarms){
          //emailText += "Alarm ID: " + value.id + "\n" +
          emailText +=  "Type: " + intervalAlarms[alarm].subType + "\n" +
                        "Severity: " + intervalAlarms[alarm].severity + "\n" +
                        "Router: " + intervalAlarms[alarm].router + "\n" +
                        "Node: " + intervalAlarms[alarm].node + "\n" +
                        "Category: " + intervalAlarms[alarm].category + "\n" +
                        "Message: " + intervalAlarms[alarm].message + "\n" +
                        "Source: " + intervalAlarms[alarm].source + "\n\n";

          emailHTML += "<table>\n" +
                       "<tr class=" + intervalAlarms[alarm].subType + "><td>Type:</td><td>" + intervalAlarms[alarm].subType + "</td></tr>\n" +
                       "<tr class=" + intervalAlarms[alarm].severity + "><td>Severity:</td><td>" + intervalAlarms[alarm].severity + "</td></tr>\n" +
                       "<tr><td>Router:</td><td>" + intervalAlarms[alarm].router + "</td></tr>\n" +
                       "<tr><td>Node:</td><td>" + intervalAlarms[alarm].node + "</td></tr>\n" +
                       "<tr><td>Category:</td><td>" + intervalAlarms[alarm].category + "</td></tr>\n" +
                       "<tr><td>Message:</td><td>" + intervalAlarms[alarm].message + "</td></tr>\n" +
                       "<tr><td>Source:</td><td>" + intervalAlarms[alarm].source + "</td></tr>\n<br>\n";
        };
        break;
    }

    if (Object.keys(intervalAlarms).length > 0 || config.sendBehaviorEnum === 'ALWAYS_SEND_ALL') {
      let mailOptions = {
        from: config.mailFrom,
        to: config.mailTo,
        subject: config.mailSubject,
        text: emailText,
        html: emailHTML
      };
      transporter.sendMail(mailOptions, (error, info) => {
        if (error) {
          return console.log(error);
        }
        console.log("Message sent: " + info.messageId);
      });
    } else {
      console.log("there were alarms this interval, but they all cleared");
    }
    // clear alarm array
    alarmArray.length = 0;
  } else {
    console.log("no alarms this interval");
  }
}

// check alarms every minute
setInterval(emailAlarms, config.mailInterval);

// handler for incoming messages from the event stream
es.onmessage = (event)=>{
  eventObj = JSON.parse(event.data)
  //console.log('event received:\n' + event.data)
  if (eventObj.alarm) {
    //console.log('alarm: ' + eventObj.alarm.id + ', subtype: ' + eventObj.subtype);
    alarmArray.push(new T128Alarm(eventObj.alarm, eventObj.subtype));
  }
};

// handler for errors with the event stream
es.onerror = (err)=>{
  if (err) {
    console.log(err)
    if (err.status === 401 || err.status === 403) {
      process.stderr.write('Error: Unable to retrieve alarms. Not authorized.\n')
      process.exit(1);
    }
  }
};

// handler for successful open of the event stream
es.onopen = ()=>{
  process.stdout.write('Monitoring for alarms.\n')
};

es.onclose = ()=>{
  process.stdout.write('Monitoring channel closed.\n')
};
