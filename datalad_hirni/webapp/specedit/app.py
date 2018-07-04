import os.path as op

from datalad.support.json_py import load_stream
import cherrypy
from cherrypy import tools

from datalad_webapp import verify_host_secret

cherrypy.tools.verify_datalad_hostsecret = cherrypy.Tool(
    'before_handler', verify_host_secret)


class SpecEditApp(object):
    _webapp_dir = op.dirname(__file__)
    _webapp_staticdir = 'static'
    _webapp_config = op.join(_webapp_dir, 'app.conf')

    def __init__(self, dataset):
        from datalad.distribution.dataset import require_dataset
        self.ds = require_dataset(
            dataset, check_installed=True, purpose='serving')

    @cherrypy.expose
    def index(self, datalad_host_secret=None):
        cherrypy.session['datalad_host_secret'] = datalad_host_secret
        from datalad_webapp import verify_host_secret
        verify_host_secret()
        return self.q()

    @cherrypy.expose
    #@cherrypy.tools.verify_datalad_hostsecret()
    def q(self, id=None):
        return """<!DOCTYPE html>
<html>
    <head>
        <link rel="stylesheet" href="css/index.css">
        <script src="js/vue.js"></script>
        <script src="js/axios.min.js"></script>
    </head>
    <body>
        <div id="app">
  <ul>
    <li v-for="spec in specs">
      <ul>
        <li v-for="(sval, skey) in spec">
          <div v-if="sval === Object(sval)">
            <!-- this is some editable property -->
            <label form="specform">{{skey}}</label>
            <input v-model="sval.value" placeholder="edit me" :disabled="sval.approved">
            <input type="checkbox" id="skey" v-model="sval.approved">
          </div>
          <div v-else>
            <!-- this is a fact -->
            <strong>NO</strong> {{ skey }}: {{ sval }}
          </div>
        </li>
      </ul>
    </li>
  </ul>
        <input type="button" @click="checkForm" value="Submit">
        </div>
        <script>
var app = new Vue({
    el: '#app',
    data: {
      specs: []
    },
    methods: {
        checkForm: function() {
            axios.post('/save', this.$data.specs)
            .then(function (response) {
              console.log(response);
            })
            .catch(function (error) {
              console.log(error);
            });
        }
    }
});
axios.get('/get_sessionspec?id=%s')
    .then(function (response) {
        app.$data.specs = response.data;
        })
    .catch(function (error) {
        console.log(error);
        })
        </script>
    </body>
</html>
""" % id

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_sessionspec(self, id):
        specpath = op.normpath(op.join(self.ds.path, id, 'studyspec.json'))
        if op.relpath(specpath, start=self.ds.path).startswith(op.pardir):
            raise ValueError(
                "Path to session specification does not point into local dataset: %s",
                specpath)
        if not op.exists(specpath):
            raise ValueError(
                'Session specification does not exist: %s', specpath)
        return list(load_stream(specpath))

    @cherrypy.expose
    @cherrypy.tools.json_in()
    def save(self):
        input_json = cherrypy.request.json

        print(input_json)
