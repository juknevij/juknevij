from flask import Flask, render_template, request
import pandas as pd
import nutrition
from pulp import *
import re
from pdfs import create_pdf

desired_width = 1000    
pd.set_option('display.width', desired_width)
myfoods= dict()
solution = dict()

df2 = pd.read_csv('menu.csv')
df = pd.read_csv('MENU.txt', names=['name', 'cost', 'ao'], delimiter="^", quotechar="~", comment='#')


df['name']=df['name'].apply(lambda x: re.sub('-', ' ', x))
df2['name']=df2['name'].apply(lambda x: re.sub('-', ' ', x))

foods=dict(zip(list(df.name),list(df.cost)))


nutrients={'energy':[2000,5000],
	'protein':[100,200],
	'carbohydrate':[225,300],
	'fat':[87,200],
	'fiber':[25,40],
	'magnesium':[500,1000],
	'calcium':[500,2000],
	'iron':[10,20],
	'vitamin c':[200,2000],
	'sugars, added':[0,40],
	'vitamin e': [15,40],
	'vitamin a': [900,10000],
	'vitamin k': [120,1000],
	'potassium':[5000,8000],
	'sodium':[0,2000],
	'zinc': [5,30],
	'copper': [0.9,3],
	'folate': [400,2000],
	'niacin': [16,30],
	'fluoride':[4,20],
	'manganese' : [2.6,20],
	 'phosphorus':[800,10000],
	 'selenium':[55,300],
	  'omega 3': [2,6],
	  'omega 6': [2,8],
	  'vitamin d':[5,40],
	  'fatty acids':[0,100],
	  'vitamin b6':[1.7,50],
	  'thiamin':[1,10],
	  'pantothenic acid':[5,50],
	  'cholesterol': [0,300],
	  'phytosterols':[10,50000],
	  'vitamin b12':[0,5],
	  'choline':[550,10000],
	  'riboflavin':[2.5,10]

}  

rdi={'energy':2000,
	'protein':50,
	'carbohydrate':275,
	'fat':78,
	'fiber':28,
	'magnesium':420,
	'calcium':1300,
	'iron':18,
	'vitamin c':90,
	'sugars, added':50,
	'vitamin e': 15,
	'vitamin a': 900,
	'vitamin k': 120,
	'potassium':4700,
	'sodium':2300,
	'zinc': 11,
	'copper': 0.9,
	'folate': 400,
	'niacin': 16,
	'fluoride':4,
	'manganese' : 2.3,
	 'phosphorus':1250,
	 'selenium':55,
	  'omega 3': 2,
	  'omega 6': 2,
	  'vitamin d':20,
	  'fatty acids':20,
	  'vitamin b6':1.7,
	  'thiamin':1.2,
	  'pantothenic acid':5,
	  'cholesterol': 300,
	  'phytosterols':10,
	  'vitamin b12':2.4,
	  'choline': 550,
	  'riboflavin':1.3

}      

def escape(s):
    # illegalChars = "-+[] ->/"
    s = s.replace("-","(hyphen)")
    s = s.replace("+","(plus)")
    s = s.replace("[","(leftBracket)")
    s = s.replace("]","(rightBracket)")
    s = s.replace(" ","(space)")
    s = s.replace(">","(greaterThan)")
    s = s.replace("/","(slash)")
    return s
    
def solver(menu,df, nut):
	
	temp = ['name'] + [key for key in nut]
#	temp = ['name'] + [key for key in nutrients]

	data=df[temp]
	
	
	
	
	

	Ingredients=data['name'].values

	data=data.set_index('name')
#	print data.protein


	data = data.fillna(0)
	

	data2=data.to_dict('dict')

	# Create the 'prob' variable to contain the problem data
	prob = LpProblem("The Whiskas Problem", LpMinimize)

	# A dictionary called 'ingredient_vars' is created to contain the referenced Variables
	ingredient_vars = LpVariable.dicts("Ingr",Ingredients,0)

	# The objective function is added to 'prob' first
	prob += lpSum([0.001*menu[i]*ingredient_vars[i] for i in Ingredients]), "Total Cost of Ingredients per can"


	# The five constraints are added to 'prob'

	for nutrient in nut:
		prob += lpSum([data2[nutrient][i] * ingredient_vars[i] for i in Ingredients]) >= nut[nutrient][0], 'min_'+nutrient
		prob += lpSum([data2[nutrient][i] * ingredient_vars[i] for i in Ingredients]) <= nut[nutrient][1], 'max_'+nutrient


	# The problem data is written to an .lp file
	prob.writeLP("WhiskasModel.lp")

	# The problem is solved using PuLP's choice of Solver
	prob.solve()

	# The status of the solution is printed to the screen
	print("Status:", LpStatus[prob.status])
	result = dict()
	# Each of the variables is printed with it's resolved optimum value
	for v in prob.variables():
		vname = re.sub('_', ' ', v.name)
		vname = re.sub('Ingr', '', vname) 
		vname = vname.strip()
#		print vname,':', v.varValue
		result[vname]=v.varValue
		
    
    
	# The optimised objective function value is printed to the screen
	print("Daily Cost of Ingredients for meals = ", value(prob.objective))


#	print 'Energy:',sum([data2['energy'][i] * value(ingredient_vars[i]) for i in Ingredients])
#	print 'Fiber:',sum([data2['fiber'][i] * value(ingredient_vars[i]) for i in Ingredients])
	nut_wg = dict()
	for nutrient in nut:
		nut_wg[nutrient] = sum([data2[nutrient][i] * value(ingredient_vars[i]) for i in Ingredients])

	
	return {'weight':result, 'status':  LpStatus[prob.status], 'nutrients': nut_wg, 'cost':value(prob.objective)}


	






app = Flask(__name__)

@app.route('/', methods=['POST', 'GET'])
def result():
	results = {}
	menu = dict()
	new_results= dict()
	checked = dict()
	checked2 = dict()
	global solution
	print solution
	
	

	if request.method == 'POST':
		results = request.form
		print 'submit:',results['submit']

		
		if results['submit']=='Print menu and nutrition facts':
			rdi_frac=dict()
			for key in solution['nutrients']:
				rdi_frac[key] = 100* solution['nutrients'][key]/rdi[key]

			return render_template("preview.html", solution = solution['weight'], nutrients = solution['nutrients'], rdi = rdi_frac)
						
		
		for key in results:
			if key.startswith("nut_"):

				if key.endswith("_min"):
					nutrients[key.split('_')[1]][0] = float(results[key])
				elif key.endswith("_max"):
					nutrients[key.split('_')[1]][1] = float(results[key])
				else:
					checked2[key.split('_')[1]] = results[key]

					
			else:
				if key != 'submit':
					menu[key] = foods[key]
					checked[key] = results[key]

		df3 = df2.loc[df2['name'].isin(menu)]
		nutrients2 = dict()
		for key in checked2: nutrients2[key] = nutrients[key]
		print nutrients2
		solution=solver(menu, df3, nutrients2)
		return render_template("index.html", menu = foods, solution = solution['weight'], checked = checked, checked2 = checked2, nutrients=nutrients, nut_sol=solution['nutrients'], status=solution['status'], cost=solution['cost'])

	else:
		return render_template("index.html", menu = foods, checked = checked, checked2 = checked2, nutrients=nutrients, solution=dict(), nut_sol=dict())

	print solution

	myfoods = new_results
	
	

		
	
#@app.route('/preview', methods=['POST', 'GET'])
#def preview():
#	render_template("preview.html")	

   
   
#   return render_template('hello.html', result = foods)

"""
@app.route("/info", methods=['POST', 'GET'])
def move_forward():
	if request.method == 'POST':
		result = request.form
		menu = dict()
		for key in result:
			if result[key]: menu[key] = foods[key]
		print menu
		df2 = pd.read_csv('menu.csv')

		df2 = df2.loc[df2['name'].isin(menu)]

		solution=solver(menu, df2)
		
		
		return render_template("info.html", menu = menu, solution = solution)
"""
if __name__ == '__main__':
   app.run(debug = True)
