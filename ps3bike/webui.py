import cherrypy
from pprint import pprint

rootpage = """
<html>
<head>
<style>
body {
   font-size: 100px;
   font-family: monospace;
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
        test : x => { console.log('test')}
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
</script>
</head>
<body onLoad="onLoad()">
<div id="app">
  Speed: {{ cstate.speed }}<br>
  Angle: {{ cstate.angle }}
 <button v-on:click="test()">TEST</button>
</div>
</body>
</html>
"""






class BikeUI(object):
    def set_cstate(self,shared_speed_mean,shared_steering_angle,shared_speed_offset,shared_speed_calibration):
        self.shared_speed_mean = shared_speed_mean
        self.shared_steering_angle = shared_steering_angle
        self.shared_speed_offset = shared_speed_offset
        self.shared_speed_calibration = shared_speed_calibration

    @cherrypy.expose
    def index(self):
        return rootpage
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def getvars(self):
       
        return {"speed": int(self.shared_speed_mean.value), "angle": int(self.shared_steering_angle.value), 
        "speed_offset": self.shared_speed_offset.value , "speed_calibration": self.shared_speed_calibration.value }
    

def start_ui(shared_speed_mean,shared_steering_angle,shared_speed_offset,shared_speed_calibration):
    conf = {'global': {'engine.autoreload.on' : False, 'server.socket_host': '0.0.0.0','server.socket_port': 80}}

    ui = BikeUI()
    ui.set_cstate(shared_speed_mean,shared_steering_angle,shared_speed_offset,shared_speed_calibration)
    cherrypy.quickstart(ui,config=conf)