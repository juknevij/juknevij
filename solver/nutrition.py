#!/usr/bin/python
#-*- coding: utf-8 -*-

"""Parses USDA flat files and converts them into an sqlite database"""

import os
import sys
import json
import sqlite3
import argparse
import pandas as pd
from pandas.io.json import json_normalize
import numpy as np
from pulp import *

import difflib

from difflib import SequenceMatcher


import re
def to_words(text):
    'Break text into a list of words without punctuation'
    return re.findall(r"[a-zA-Z']+", text)

def match(a, b):
    # Make b the longer list.
    if len(a) > len(b):
        a, b = b, a
    # Map each word of b to a list of indices it occupies.
    b2j = {}
    for j, word in enumerate(b):
        b2j.setdefault(word, []).append(j)
    j2len = {}
    nothing = []
    unique = set() # set of all results
    def local_max_at_j(j):
        # maximum match ends with b[j], with length j2len[j]
        length = j2len[j]
        unique.add(" ".join(b[j-length+1: j+1]))
    # during an iteration of the loop, j2len[j] = length of longest
    # match ending with b[j] and the previous word in a
    for word in a:
        # look at all instances of word in b
        j2lenget = j2len.get
        newj2len = {}
        for j in b2j.get(word, nothing):
            newj2len[j] = j2lenget(j-1, 0) + 1
        # which indices have not been extended?  those are
        # (local) maximums
        for j in j2len:
            if j+1 not in newj2len:
                local_max_at_j(j)
        j2len = newj2len
    # and we may also have local maximums ending at the last word
    for j in j2len:
        local_max_at_j(j)
    return unique


desired_width = 1000    
pd.set_option('display.width', desired_width)






# Nutrient name mapping to internal names.
# Note: some mappings are special cases, not handled by `mapping`, e.g. 'protein'
_mapping = {
    # Elements
    'calcium': {'Calcium, Ca'},
    'copper': {'Copper, Cu'},
    'fluoride': {'Fluoride, F'},
    'iron': {'Iron, Fe'},
    'magnesium': {'Magnesium, Mg'},
    'manganese': {'Manganese, Mn'},
    'phosphorus': {'Phosphorus, P'},
    'selenium': {'Selenium, Se'},
    'zinc': {'Zinc, Zn'},
    'potassium': {'Potassium, K'},
    'sodium': {'Sodium, Na'},
    
    # Vitamins
    'vitamin a': {'Vitamin A, RAE'},  # Note: this includes Retinol
    'vitamin a, preformed': {'Retinol'},
    'vitamin c': {'Vitamin C, total ascorbic acid'},
    'vitamin d': {'Vitamin D (D2 + D3)'},
    'vitamin e': {'Vitamin E (alpha-tocopherol)'},
    'vitamin e, added': {'Vitamin E, added'},
    'vitamin k': {'Vitamin K (phylloquinone)'},
    'thiamin': {'Thiamin'},
    'riboflavin': {'Riboflavin'},
    'niacin': {'Niacin'},
    'vitamin b6': {'Vitamin B-6'},
    'folate': {'Folate, DFE'},
    'folate, added': {'Folic acid'},
    'pantothenic acid': {'Pantothenic acid'},
    'choline': {'Choline, total'},
    'carotenoids': {'Carotene, beta', 'Carotene, alpha', 'Cryptoxanthin, beta', 'Lycopene', 'Lutein + zeaxanthin'},
    
    # Note: though 'Vitamin B-12, added' sometimes exceeds 'Vitamin B-12'
    # slightly, the former is included in the latter, the latter being the
    # total vitamin B12 regardless of whether it was added or not. We
    # consider those slight excesses to be minor errors in the USDA data
    # files
    'vitamin b12': {'Vitamin B-12'},
    
    # Macronutrients and other
    'energy': {'Energy'},
    'water': {'Water'},
    'carbohydrate': {'Carbohydrate, by difference'},
    'fiber': {'Fiber, total dietary'},
    'fat': {'Total lipid (fat)'},
    'omega 6': {'18:2 undifferentiated'},
    'omega 3': {'18:3 n-3 c,c,c (ALA)'},
    'linoleic acid + alpha linolenic acid': {'18:2 undifferentiated', '18:3 n-3 c,c,c (ALA)'},
    'cholesterol': {'Cholesterol'},
    'fatty acids': {'Fatty acids, total trans', 'Fatty acids, total saturated'},
    'sugars, added': {'Sugars, total'},  # we assume the worst by using total sugars as "[added] sugar is chemically indistinguishable from naturally-occurring sugars" https://en.wikipedia.org/wiki/Added_sugar
    
    'caffeine': {"Caffeine"},
    'phytosterols':{'Phytosterols'}
    
}



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
	  'choline':[550,10000]

}    

fields = {

    'FOOD_DES.txt': [
        'NDB_No',
        'FdGrp_Cd',
        'Long_Desc',
        'Shrt_Desc',
        'ComName',
        'ManufacName',
        'Survey',
        'Ref_desc',
        'Refuse',
        'SciName',
        'N_Factor',
        'Pro_Factor',
        'Fat_Factor',
        'CHO_Factor',
    ],
    'FD_GROUP.txt': [
        'FdGrp_Cd',
        'FdGrp_Desc',
    ],
    'LANGUAL.txt': [
        'NDB_No',
        'Factor_Code',
    ],
    'LANGDESC.txt': [
        'Factor_Code',
        'Description',
    ],
    'NUT_DATA.txt': [
        'NDB_No',
        'Nutr_No',
        'Nutr_Val',
        'Num_Data_Pts',
        'Std_Error',
        'Src_Cd',
        'Deriv_Cd',
        'Ref_NDB_No',
        'Add_Nutr_Mark',
        'Num_Studies',
        'Min',
        'Max',
        'DF',
        'Low_EB',
        'Up_EB',
        'Stat_cmt',
        'AddMod_Date',
        'CC',
    ],
    'NUTR_DEF.txt': [
        'Nutr_No',
        'Units',
        'Tagname',
        'NutrDesc',
        'Num_Dec',
        'SR_Order',
    ],
    'SRC_CD.txt': [
        'Src_Cd',
        'SrcCd_Desc',
    ],
    'DERIV_CD.txt': [
        'Deriv_Cd',
        'Deriv_Desc',
    ],
    'WEIGHT.txt': [
        'NDB_No',
        'Seq',
        'Amount',
        'Msre_Desc',
        'Gm_Wgt',
        'Num_Data_Pts',
        'Std_Dev',
    ],
    'FOOTNOTE.txt': [
        'NDB_No',
        'Footnt_No',
        'Footnt_Typ',
        'Nutr_No',
        'Footnt_Txt',
    ],
    'DATSRCLN.txt': [
        'NDB_No',
        'Nutr_No',
        'DataSrc_ID',
    ],
    'DATA_SRC.txt': [
        'DataSrc_ID',
        'Authors',
        'Title',
        'Year',
        'Journal',
        'Vol_City',
        'Issue_State',
        'Start_Page',
        'End_Page',
    ],
}

groups= {'FOOD_DES.txt': 'food_des',
		 'FD_GROUP.txt': 'fd_group',
		 'LANGUAL.txt': 'langual',
		 'LANGDESC.txt': 'langdesc',
		 'LANGDESC.txt': 'langdesc',
		 'NUT_DATA.txt': 'nut_data',
		 'NUTR_DEF.txt': 'nutr_def',
		 'SRC_CD.txt': 'src_cd',
		 'DERIV_CD.txt': 'deriv_cd',
		 'WEIGHT.txt': 'weight',
		 'FOOTNOTE.txt': 'footnote',
		 'DATA_SRC.txt': 'data_src',
		 'DATSRCLN.txt': 'datsrcln'
			 }
# Normalise values: transform ``value / (100 unit)`` to ``value/SI_unit``
units = {
        'g': 1,
        'mg': 1,
        'µg': 1,
        'kg': 1,
        'l': 1,
        'cal': 1e-3,
        'kcal': 1,
        '\xb5g': 1}

def query(filename):
	return pd.read_csv(filename, names=fields[filename], dtype=str, delimiter="^", quotechar="~", comment='#')

def get_all(): 
	alldata={}
	for grp in groups:
		df=query(grp)
		alldata[groups[grp]] = df

	nut_data=alldata['nut_data'][['NDB_No','Nutr_No', 'Nutr_Val']]
	food_des=alldata['food_des'][['NDB_No','FdGrp_Cd', 'Long_Desc','Fat_Factor', 'Pro_Factor', 'CHO_Factor']]
	fd_group=alldata['fd_group'][['FdGrp_Cd','FdGrp_Desc']]
	nutr_def=alldata['nutr_def'][['Nutr_No','Units','NutrDesc']]

	
		# Drop unused nutrients
	used_nutrients = set.union({'Protein', 'Adjusted Protein'}, *_mapping.values())
	used_nutrients = {x for x in used_nutrients if not x.endswith(': energy')}
	nutr_def = nutr_def[nutr_def['NutrDesc'].isin(used_nutrients)]

		
	food_des=pd.merge(food_des, fd_group, on='FdGrp_Cd', how='left')
	


	nut_data=pd.merge( nutr_def, nut_data, left_on='Nutr_No', right_on='Nutr_No')

	nut_data['Nutr_Val']=nut_data['Nutr_Val'].astype(float)
	nut_data['Nutr_No']=nut_data['Nutr_No'].astype(int)
	
	
	nut_data = nut_data[nut_data['Nutr_No'] != 268]  # Energy appears twice in sr28, don't use the one with id 268
	nut_data = nut_data[nut_data['Nutr_No'] != 318]  # Vitamin A, I
	nut_data = nut_data[nut_data['Nutr_No'] != 324]  # Vitamin D


	nut_data['Units'] = nut_data['Units'].apply(lambda x: units[x])

	nut_data['Nutr_Val'] = nut_data['Nutr_Val'] * nut_data['Units']/100
	nut_data.drop('Units', 1, inplace=True)
	nut_data.drop('Nutr_No', 1, inplace=True)
	
	
	
	nut_data = nut_data.pivot(index='NDB_No', columns='NutrDesc', values='Nutr_Val')

	
	# Map to internal nutrient names
	for name, usda_names in _mapping.items():
		usda_names = list(usda_names)
		sub_values = nut_data[usda_names].dropna(how='all')
		nan_counts = sub_values.isnull().sum()
		if nan_counts.any():
			sub_values = sub_values.fillna(0)
		nut_data[name] = sub_values.sum(axis=1)
	
	
# Map special case: protein
	nut_data['protein'] = nut_data['Adjusted Protein'].fillna(nut_data['Protein'])
	
	

 # Drop usda nutrient columns, leaving just the internal ones
	nut_data = nut_data.drop(used_nutrients, axis=1)	
	
	
	
	nut_data = nut_data.sort_index(axis=1)
	
	
	for column in food_des.columns:
		if column.endswith('_Factor'):
			food_des[column] = food_des[column].astype(float)*1e3
	
	
	food_des.set_index('NDB_No', inplace=True)
	foods=pd.concat([nut_data, food_des], axis=1, join='inner')
	
		
	


 
	

	foods = foods.rename(columns={'Long_Desc': 'name', 'FdGrp_Desc': 'group'})
	foods = foods.drop('FdGrp_Cd', axis=1)	

    

	return foods	


def solver(cost):
	
	df=get_all()

	temp = ['name'] + [key for key in nutrients]

	data=df[df['name'].isin(cost)][temp]

	Ingredients=data['name'].values

	data=data.set_index('name')

	data = data.fillna(0)
	
	pd.DataFrame.to_csv(data, "menu.csv", header=True)

	data2=data.to_dict('dict')

	# Create the 'prob' variable to contain the problem data
	prob = LpProblem("The Whiskas Problem", LpMinimize)

	# A dictionary called 'ingredient_vars' is created to contain the referenced Variables
	ingredient_vars = LpVariable.dicts("Ingr",Ingredients,0)

	# The objective function is added to 'prob' first
	prob += lpSum([0.001*cost[i]*ingredient_vars[i] for i in Ingredients]), "Total Cost of Ingredients per can"


	# The five constraints are added to 'prob'

	for nutrient in nutrients:
		prob += lpSum([data2[nutrient][i] * ingredient_vars[i] for i in Ingredients]) >= nutrients[nutrient][0], 'min_'+nutrient
		prob += lpSum([data2[nutrient][i] * ingredient_vars[i] for i in Ingredients]) <= nutrients[nutrient][1], 'max_'+nutrient


	# The problem data is written to an .lp file
	prob.writeLP("WhiskasModel.lp")

	# The problem is solved using PuLP's choice of Solver
	prob.solve()

	# The status of the solution is printed to the screen
	print("Status:", LpStatus[prob.status])

	# Each of the variables is printed with it's resolved optimum value
	for v in prob.variables():
		print(v.name, "=", v.varValue)
    
    
	# The optimised objective function value is printed to the screen
	print("Daily Cost of Ingredients for meals = ", value(prob.objective))


	print 'Energy:',sum([data2['energy'][i] * value(ingredient_vars[i]) for i in Ingredients])
	print 'Fiber:',sum([data2['fiber'][i] * value(ingredient_vars[i]) for i in Ingredients])




 



       
