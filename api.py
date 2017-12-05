from flask import Flask, request, abort
from simulateur import Simulator
from webargs import fields, validate
from webargs.flaskparser import use_args
from openfisca_france.model.base import CATEGORIE_SALARIE
from flasgger import Swagger
from flask_cors import CORS
import json

app = Flask(__name__)
simulator = Simulator()
CORS(app)

app.config['SWAGGER'] = {
	'title': 'Api',
	'uiversion': 2
}
Swagger(app, template_file='api_docs/documentation.yml')

def validate_category(cat):
	for type_sal_name, type_sal_index in CATEGORIE_SALARIE:
		if cat == type_sal_name:
			return True
	return False

parent_constraint = fields.Nested({
	'age': fields.Int(required=True,validate=lambda val: val >= 0),
	'salaire_de_base': fields.Int(required=True, validate=lambda val: val >= 0),
	'categorie_salarie': fields.Str(required=True, validate=validate_category),
	'retraite_brute': fields.Int(validate=lambda val: val >= 0),
	'chomage_brut': fields.Int(validate=lambda val: val >= 0),
	'statut_marital': fields.Int(validate=lambda val: val >= 0 and val <= 6),
	'taux_incapacite': fields.Float(validate=lambda val: val >= 0 and val <= 1)
})

simulation_args = {
	'parent1': parent_constraint,
	'parent2': parent_constraint,
	'enfants': fields.Int(missing=0, validate=lambda val: val >= 0),
	'menage': fields.Nested({
		'loyer': fields.Int(),
		'cotisation_taxe_habitation': fields.Int(),
		'statut_occupation_logement': fields.Int(validate=lambda val: val >= 1 and val <= 7),
		'zone_apl': fields.Int(validate=lambda val: val >= 1 and val <= 3)
	})
}

@app.errorhandler(422)
def handle_validation_error(err):
	exc = err.exc
	return json.dumps({'errors': exc.messages}), 422

@app.route("/", methods=['GET'])
def root():
	return '<a href="/apidocs/#!/simulation/post_simulation">Documentation</a>'

@app.route("/categorie_salarie", methods=['GET'])
def categorie_salarie():
	return json.dumps({ "categories": [k for k,v in CATEGORIE_SALARIE] })

@app.route("/simulation", methods=['POST'])
@use_args(simulation_args)
def simulation(args):
	if request.method != 'POST':
		abort(405)
	if not 'parent1' in args or args['parent1'] == None:
		return json.dumps({ "errors": "parent1 should be defined" }), 422
	return simulator.run(args)
