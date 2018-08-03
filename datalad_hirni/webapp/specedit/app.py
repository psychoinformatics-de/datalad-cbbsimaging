import os.path as op

from datalad.support.json_py import load_stream
from datalad.support.json_py import dump2stream
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
    @cherrypy.tools.json_out()
    def get_sessionspec(self, id):
        specpath = self.specpath_from_id(id)
        if not op.exists(specpath):
            raise ValueError(
                'Session specification does not exist: %s', specpath)
        return list(load_stream(specpath))

    @cherrypy.expose
    @cherrypy.tools.json_in()
    def save(self, id):
        specpath = self.specpath_from_id(id)
        dump2stream(cherrypy.request.json, specpath, compressed=False)


    def specpath_from_id(self, id):
        specpath = op.normpath(op.join(self.ds.path, id, 'studyspec.json'))
        if op.relpath(specpath, start=self.ds.path).startswith(op.pardir):
            raise ValueError(
                "Path to session specification does not point into local dataset: %s",
                specpath)
        return specpath
