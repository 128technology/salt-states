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
var routerFilter = config.routerFilter;

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

function filterClearedAlarms(alarms) {
  var intervalAlarms = {};
  var unclearedAlarms = [];
  alarms.forEach(function(value){
    if (value.subType === "ADD") {
      // We got an add alarm so push it
      intervalAlarms[value.id] = value;
    } else if (value.subType === "CLEAR") {
      if (Object.keys(intervalAlarms).includes(value.id) && intervalAlarms[value.id].subType === "ADD") {
        //console.log('popping alarm because clear came within interval');
        delete intervalAlarms[value.id];
      } else {
        //console.log('we got a clear that doesn\'t match an existing alarm, add it to the queue');
        intervalAlarms[value.id] = value;
      }
    }
  });
  for (var alarm in intervalAlarms) {
    unclearedAlarms.push(intervalAlarms[alarm])
  }
  return unclearedAlarms;
}

function filterAlarmsByRouter(alarms) {
  filteredAlarms = [];
  alarms.forEach(function(value) {
    if (routerFilter.indexOf(value.router) > -1) {
      filteredAlarms.push(value);
    }
  });
  return filteredAlarms;
}

// function to email any pending alarms
function emailAlarms(alarms) {
  if (alarms.length > 0) {
    emailText = "";
    emailHTML = "<style>\n" +
                "table, th, td { border: 1px solid black; }\n" +
                ".CRITICAL { background-color: red; }\n" +
                ".MAJOR { background-color: orange; }\n" +
                ".MINOR { background-color: yellow; }\n" +
                ".ADD { background-color: Crimson; }\n" +
                ".CLEAR { background-color: CornflowerBlue; }\n" +
                "</style>" +
                "<table>\n";
    alarms.forEach(function(value){
      //emailText += "Alarm ID: " + value.id + "\n" +
      emailText +=  "Type: " + value.subType + "\n" +
                    "Severity: " + value.severity + "\n" +
                    "Router: " + value.router + "\n" +
                    "Node: " + value.node + "\n" +
                    "Category: " + value.category + "\n" +
                    "Message: " + value.message + "\n" +
                    "Source: " + value.source + "\n\n";

      emailHTML += "<tr class=" + value.subType + "><td>Type:</td><td>" + value.subType + "</td></tr>\n" +
                   "<tr class=" + value.severity + "><td>Severity:</td><td>" + value.severity + "</td></tr>\n" +
                   "<tr><td>Router:</td><td>" + value.router + "</td></tr>\n" +
                   "<tr><td>Node:</td><td>" + value.node + "</td></tr>\n" +
                   "<tr><td>Category:</td><td>" + value.category + "</td></tr>\n" +
                   "<tr><td>Message:</td><td>" + value.message + "</td></tr>\n" +
                   "<tr><td>Source:</td><td>" + value.source + "</td></tr>\n<br>\n";
    });

    emailHTML += "</table>";

    //if we only have one alarm, send some info in the subject header (most likely interval is zero)
    if (alarms.length === 1) {
      emailSubject = "[" + alarms[0].router + "] " + alarms[0].subType + ": " + alarms[0].message;
    } else {
      emailSubject = config.mailSubject;
    }

    let mailOptions = {
      from: config.mailFrom,
      to: config.mailTo,
      subject: emailSubject,
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
    console.log("no alarms this interval");
  }
}

function handleInterval() {
  if (routerFilter.length > 0) {
    alarmArray = filterAlarmsByRouter(alarmArray);
  }
  if (config.sendBehaviorEnum === 'ALWAYS_SEND_ALL') {
    emailAlarms(alarmArray);
  } else {
    unclearedAlarms = filterClearedAlarms(alarmArray);
    if (unclearedAlarms.length > 0) {
      if (config.sendBehaviorEnum === 'NO_CLEAR_INTERVAL') {
        emailAlarms(unclearedAlarms);
      } else if (config.sendBehaviorEnum === 'SEND_CLEAR_INTERVAL') {
        emailAlarms(alarmArray);
      }
    }
  }
  alarmArray.length = 0;
}
        
// check alarms every interval, if more than zero
if (config.mailInterval > 0) {
  setInterval(handleInterval, config.mailInterval);
}

// handler for incoming messages from the event stream
es.onmessage = (event)=>{
  eventObj = JSON.parse(event.data)
  //console.log('event received:\n' + event.data)
  if (eventObj.alarm) {
    //console.log('alarm: ' + eventObj.alarm.id + ', subtype: ' + eventObj.subtype);
    if (config.mailInterval > 0) {
      alarmArray.push(new T128Alarm(eventObj.alarm, eventObj.subtype));
    } else {
      //if we're not using intervals send all alarms immediately
      emailAlarms([new T128Alarm(eventObj.alarm, eventObj.subtype)]);
    } 
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
