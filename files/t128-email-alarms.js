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
      // We'll add all alarms to the email text
      // If we're going to send an e-mail we may inform about all alarms/clears
      emailText += "id: " + value.id + "\n";
      emailText += "subType: " + value.subType + "\n";
      emailText += "router: " + value.router + "\n";
      emailText += "node: " + value.node + "\n";
      emailText += "severity: " + value.severity + "\n";
      emailText += "category: " + value.category + "\n";
      emailText += "message: " + value.message + "\n";
      emailText += "source: " + value.source + "\n\n";
    });
    if (Object.keys(intervalAlarms).length > 0 || config.sendBehaviorEnum === 'ALWAYS_SEND_ALL') {
      console.log("email text:\n" + emailText);
      let mailOptions = {
        from: config.mailFrom,
        to: config.mailTo,
        subject: config.mailSubject,
        text: emailText
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
    console.log('alarm: ' + eventObj.alarm.id + ', subtype: ' + eventObj.subtype);
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
