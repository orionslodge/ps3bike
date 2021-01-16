import cherrypy
from pprint import pprint

rootpage = """
<html>
<head>
<style>
body {
   font-size: 50px;
   font-family: monospace;
}

button {
  border: 1px;
  padding: 0px;
  font-family: monospace;
  text-align: center;
  text-decoration: none;
  display: inline-block;
  font-size: 50px;
  margin: 20px 2px;
  border-radius: 50%;
}

</style>
<script src="https://cdn.jsdelivr.net/npm/vue@2/dist/vue.js"></script>
<script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>
<script>

function onLoad() {
    var app = new Vue({
    el: '#app',
    data: {
        cstate : { speed: -1, steer:- 1}
    },
    methods : {
        update:update,
        setvar:setvar
    },
    mounted() {
    this.interval = setInterval(() => this.update(), 1000);
    }
    })
    }

 async function update() {
    response =  await axios.get("/getvars") 
    console.log(response.data)
    this.cstate = response.data
}

async function setvar(name,value) {
     response =  await axios.get(`/setvar?name=${name}&value=${value}`) 
}

</script> 
</head>
<body onLoad="onLoad()">
<div id="app">
  Speed: {{ cstate.speed }}<br>
  Steer: {{ cstate.angle }}<br>
  MinThrottle: {{ cstate.speed_offset }} 
  <button v-on:click="setvar('speed_offset',cstate.speed_offset+5)">+</button>
  <button v-on:click="setvar('speed_offset',cstate.speed_offset-5)">-</button><br>
  ThrottleScale: {{ cstate.speed_calibration }}
  <button v-on:click="setvar('speed_calibration',cstate.speed_calibration+1)">+</button>
  <button v-on:click="setvar('speed_calibration',cstate.speed_calibration-1)">-</button><br>
</div>
</body>
</html>
"""
 





class BikeUI(object):


    def set_cstate(self,shared_speed_mean,shared_steering_angle,shared_speed_offset,shared_speed_calibration,bike):
        self.shared_speed_mean = shared_speed_mean
        self.shared_steering_angle = shared_steering_angle
        self.shared_speed_offset = shared_speed_offset
        self.shared_speed_calibration = shared_speed_calibration
        self.bike = bike

    @cherrypy.expose
    def index(self):
        return rootpage
    
    @cherrypy.expose
    def setvar(self,name=None,value=None):
        print(f"setting self.{name} to {value}")
        try:
            getattr(self, "shared_"+name,{}).value = int(value)
            self.bike.save_settings()
        except Exception as e:
            print("Unknown variable " + str(e))

   
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def getvars(self):
       
        return {"speed": int(self.shared_speed_mean.value), "angle": int(self.shared_steering_angle.value), 
        "speed_offset": self.shared_speed_offset.value , "speed_calibration": self.shared_speed_calibration.value }
    

def start_ui(shared_speed_mean,shared_steering_angle,shared_speed_offset,shared_speed_calibration,bike):
    conf = {'global': {'engine.autoreload.on' : False, 'server.socket_host': '0.0.0.0','server.socket_port': 80}}

    ui = BikeUI()
    ui.set_cstate(shared_speed_mean,shared_steering_angle,shared_speed_offset,shared_speed_calibration,bike)
    cherrypy.quickstart(ui,config=conf)