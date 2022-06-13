import requests 
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from io import StringIO
from datetime import datetime

sns.set(rc={'axes.facecolor':'white', 'figure.facecolor':'white'})



'''
Helper Functions
'''

# this is needed as some dates in the NHTSA database are of the form YYYY-MM-DDTHH:MM:SSZ
def conv_datetime(string):
	return datetime.strptime(string.split('T')[0],'%Y-%m-%d').strftime('%Y-%m')

def get_models(make, year):
	
	url = 'https://api.nhtsa.gov/products/vehicle/models?modelYear='+str(year)+'&make='+make+'&issueType=c'
	s = requests.get(url).text
	J = pd.read_json(StringIO(s))

	L = [ 
			J['results'][i]['model'] for i in range(len(J['results'])) 
	]

	return L

def get_makes(year):
	
	url = 'https://api.nhtsa.gov/products/vehicle/makes?modelYear='+str(year)+'&issueType=c'
	s = requests.get(url).text
	J = pd.read_json(StringIO(s))

	L = [ 
			J['results'][i]['make'] for i in range(len(J['results'])) 
	]

	return L


'''
Class Definitions
'''

class Vehicle:
	def __init__(self, year, make, model):
		self.year = year
		self.make = make
		self.model = model

	def __repr__(self):
		return "Vehicle({year}, '{make}', '{model}')".format(year=self.year, make=self.make, model=self.model)

	def __str__(self):
		return "{year} {make} {model}".format(year=self.year, make=self.make.upper(), model=self.model.upper())

	def __eq__(self,other):
		return (self.year==other.year) and (self.make==other.make) and (self.model==other.model)

	def get_complaint_df(self):
		
		url = 'https://www.nhtsa.gov/webapi/api/Complaints/vehicle/modelyear/'+str(self.year)+'/make/'+self.make+'/model/'+self.model+'?format=csv'
		s = requests.get(url).text
		complaints = pd.read_csv(StringIO(s))
		
		return complaints

	def get_recall_df(self):

		url = 'https://www.nhtsa.gov/webapi/api/Recalls/vehicle/modelyear/'+str(self.year)+'/make/'+self.make+'/model/'+self.model+'?format=csv'
		s = requests.get(url).text
		recalls = pd.read_csv(StringIO(s))

		return recalls

	'''
	Here, the year is the model year, and endyear is the upper bound on the dates we plot
	
	"datetype" refers to either the date the complaint was 'recieved' or the date the 'incident' ocurred
	'''
	def comp_per_month(self, endyear, component, datetype):
		
		if endyear < self.year:
			print("The endyear cannot be before the production year!")
			return    

		data = self.get_complaint_df()
		
		data['RECVD_DT'] = data['RECVD_DT'].apply(conv_datetime)
		data['INCIDENT_DT'] = data['INCIDENT_DT'].apply(conv_datetime)
 
		d = {}
		ts = pd.date_range(str(self.year)+'-01',str(endyear)+'-01',freq='MS').to_period('M')
		d['Date']=ts

		if datetype=='received':
			d['Total'] = [ len([ 1 for n in range(len(data)) if str(date)[0:7]==data['RECVD_DT'][n] ]) 
						   for date in ts]
			d['Component'] = [ len([ 1 for n in range(len(data)) 
								if str(date)[0:7]==data['RECVD_DT'][n] and component in data['COMPONENT'][n]]) 
								   for date in ts]
		elif datetype=='incident':
			d['Total'] = [ len([ 1 for n in range(len(data)) if str(date)[0:7]==data['INCIDENT_DT'][n] ]) 
						   for date in ts]
			d['Component'] = [ len([ 1 for n in range(len(data)) 
								if str(date)[0:7]==data['INCIDENT_DT'][n] and component in data['COMPONENT'][n]]) 
								   for date in ts]
		
		df = pd.DataFrame(d)
		
		fig, ax = plt.subplots(figsize=(17,8))
		plt.xticks(rotation=80)
		sns.set_color_codes('pastel')
		sns.barplot(x='Date',y='Total',data=df,color='b',label='Total')
		sns.set_color_codes('muted')
		sns.barplot(x='Date',y='Component',data=df,color='b',label=component.lower().capitalize())
		ax.set(ylabel='',xlabel='',title='Complaints per Month for the '+str(self.year)+' '+self.make.capitalize()+' '+self.model.capitalize())
		ax.legend(loc='upper left')
		plt.show()





class VehicleList:
	def __init__(self, vehicle_list):
		self.vehicle_list = vehicle_list

	def __repr__(self):
		return "{}".format(self.vehicle_list)

	def __str__(self):
		L = [str(v) for v in self.vehicle_list]
		return "{}".format(L)

	def __eq__(self,other):
		return self.vehicle_list==other.vehicle_list

	
	# this method returns a dictionary of the form {vehicle : complaint dataframe for vehicle} 
	def get_complaints(self):
		
		data = {} 
		for i in self.vehicle_list:
			data[i] = i.get_complaint_df()
		
		return data

	# this method returns a dictionary of the form {vehicle : recall dataframe for vehicle} 
	def get_recalls(self):
		
		data = {} 
		for i in self.vehicle_list:
			data[i] = i.get_recall_df()
		
		return data

	# this method produces a list of components present in the complaints dataframe produced by the get_complaints() method
	def component_parts(self, keyword):

		data = self.get_complaints()
		components = []
		
		for key in data.keys(): 
			for j in range(len(data[key])):
				# split off the component names and dump the contents into a list:
				components += data[key]['COMPONENT'][j].split(' | ') 
		
		# if we specify a component it will extract all minor components of the type specified
		if keyword != 'ALL':
			component_parts = [component for component in components if (keyword in component and component!=keyword)] 
			component_parts = sorted(component_parts)
			component_parts = pd.Series(component_parts).drop_duplicates().reset_index(drop=True)

		#'ALL' returns all of the major components of the vehicle present in the complaints
		if keyword == 'ALL':
			component_parts = [ component.split(':')[0] for component in components ] # split off major components
			component_parts = sorted(component_parts)
			component_parts = pd.Series(component_parts).drop_duplicates().reset_index(drop=True)
			
		return component_parts

	'''
	keyword - same parameter as in the component_parts() method

	value - specifies what to count: complaints, injuries, crashes, fires, or deaths
	
	air_bags - boolean value indicating whther or not to include 'AIR BAGS' component; due to a massive air bag recall by Takata, 
	the 'AIR BAGS' column tends to overwhelm the other heatmap values so that only the air bags row is 'hot' 
	'''
	def create_heatmap(self, keyword, value, air_bags=True):
		
		if value not in ['complaints','fires','injuries','deaths','crashes']:

			print('The last argument must be one of the following:')
			print('"complaints", "fires", "crashes", "injuries", or "deaths"')
			
			return
		
		data = self.get_complaints()
		components = self.component_parts(keyword)
		total_data={}

		if value=='complaints':
			for j in range( len(components) ):
				total_data[components[j]] = [ len([
													1 for n in range(len(data[key])) if components[j] in data[key]['COMPONENT'][n]
												  ]) 
													 for key in data.keys()]
		if value=='fires':
			for j in range( len(components) ):
				total_data[components[j]] = [ len([
													1 for n in range(len(data[key])) if (data[key]['FIRE_YN'][n]=='Yes' and components[j] in data[key]['COMPONENT'][n]) 
												  ]) 
													 for key in data.keys()]
		if value=='crashes':
			for j in range( len(components) ):
				total_data[components[j]] = [ len([
													1 for n in range(len(data[key])) if (data[key]['CRASH_YN'][n]=='Yes' and components[j] in data[key]['COMPONENT'][n]) 
												  ]) 
													 for key in data.keys()]
		if value=='injuries':
			for j in range( len(components) ):
				total_data[components[j]] = [ np.array([ 
													data[key]['NUM_INJURED'][n] for n in range(len(data[key])) if components[j] in data[key]['COMPONENT'][n]
													 	]).sum(dtype=np.int) 
															for key in data.keys()]
		if value=='deaths':
			for j in range( len(components) ):
				total_data[components[j]] = [ np.array([ 
													data[key]['NUM_DEATHS'][n] for n in range(len(data[key])) if components[j] in data[key]['COMPONENT'][n]
													   ]).sum(dtype=np.int) 
															for key in data.keys()]
		

		if air_bags == False:
			total_data = {key:total_data[key] for key in total_data.keys() if key!='AIR BAGS'}

		new_index = [str(key) for key in data.keys()] 
		df = pd.DataFrame(data=total_data,index=new_index).transpose()

		# generating the heatmap
		title = value.capitalize()+' Per Component'
		plt.subplots(figsize=(22,14))
		sns.heatmap(df,linewidths=0.9,cmap='Reds',fmt='d',annot=True)
		plt.xlabel('Model')
		plt.ylabel('Component')
		plt.title(title)