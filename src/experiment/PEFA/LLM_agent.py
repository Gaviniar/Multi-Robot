from LLM import *
import re
import copy
import json # Added import


class LLM_agent:
	"""
	LLM agent class
	"""
	def __init__(self, agent_id, args, agent_node, init_graph):

		self.agent_node = agent_node
		self.agent_id = agent_id
		self.init_graph = init_graph
		self.init_id2node = {x['id']: x for x in init_graph['nodes']}
		self.source = args.source
		self.lm_id = args.lm_id
		self.args = args
		self.LLM = LLM(self.source, self.lm_id, self.args)
		self.unsatisfied = {}
		self.steps = 0
		self.plan = None
		self.current_room = None
		self.grabbed_objects = None
		self.goal_location = None
		self.goal_location_id = None
		self.last_action = None
		self.id2node = {}
		self.id_inside_room = {}
		self.satisfied = []
		self.reachable_objects = []


	def LLM_plan(self):

		return self.LLM.run(self.agent_node, self.chat_agent_info, self.current_room, self.next_rooms, self.all_landable_surfaces,self.landable_surfaces, 
					  self.on_surfaces, self.grabbed_objects, self.reachable_objects, self.unreached_objects, self.on_same_surfaces)


	def check_progress(self, state, goal_spec):
		unsatisfied = {}
		satisfied = []
		id2node = {node['id']: node for node in state['nodes']}

		for key, value in goal_spec.items():
			elements = key.split('_')
			self.goal_location_id = int((re.findall(r'\((.*?)\)', elements[-1]))[0])
			self.target_object_id = int((re.findall(r'\((.*?)\)', elements[1]))[0])
			cnt = value[0]
			for edge in state['edges']:
				if cnt == 0:
					break
				if edge['relation_type'].lower() == elements[0] and edge['to_id'] == self.goal_location_id and edge['from_id'] == self.target_object_id:
					satisfied.append(id2node[edge['from_id']])  # A list of nodes that meet the goal
					cnt -= 1
					# if self.debug:
					# 	print(satisfied)
			if cnt > 0:
				unsatisfied[key] = value  
		return satisfied, unsatisfied


	def get_action(self, observation, chat_agent_info, goal):

		satisfied, unsatisfied = self.check_progress(observation, goal) 
		# print(f"satisfied: {satisfied}")
		if len(satisfied) > 0:
			self.unsatisfied = unsatisfied
			self.satisfied = satisfied

		obs = observation
		self.grabbed_objects = None
		self.reachable_objects = []
		self.landable_surfaces = None
		self.on_surfaces = None
		self.all_landable_surfaces = []
		self.all_landable_surfaces = [x for x in obs['nodes'] if 'LANDABLE' in x['properties']]
		self.on_same_surfaces = []
		self.on_same_surfaces_ids = []
		self.chat_agent_info = chat_agent_info

		self.id2node = {x['id']: x for x in obs['nodes']}

		for e in obs['edges']:
			x, r, y = e['from_id'], e['relation_type'], e['to_id']
			
			if x == self.agent_node['id']:

				if r == 'INSIDE':
					self.current_room = self.id2node[y]
				if r == 'ON' :
					self.on_surfaces = self.id2node[y]
					if self.agent_node['class_name'] == 'robot arm' or self.agent_node['class_name'] == 'robot_arm':
						for i in range(3):
							for edge in obs['edges']:
								if (edge['from_id'] != x and edge['to_id'] == y and edge['relation_type'] == 'ON') or (edge['from_id'] != x and edge['to_id'] in self.on_same_surfaces_ids and edge['relation_type'] == 'ON') or (edge['from_id'] != x and edge['to_id'] in self.on_same_surfaces_ids and edge['relation_type'] == 'INSIDE') :
									self.on_same_surfaces_ids.append(edge['from_id'])
									#self.on_same_surfaces.append(self.id2node[edge['from_id']])  # Find any contain or surface on the table
									if 'SURFACES' in self.id2node[edge['from_id']]['properties'] or 'CONTAINERS' in self.id2node[edge['from_id']]['properties']:
										for ee in obs['edges']:
											if ee['to_id'] == edge['from_id'] and (ee['relation_type'] == 'INSIDE' or ee['relation_type'] == 'ON'):
												self.on_same_surfaces_ids.append(ee['from_id'])
												#self.on_same_surfaces.append(self.id2node[ee['from_id']]) # The goal here is to find objects that are not directly on the surface
								self.on_same_surfaces_ids = list(set(self.on_same_surfaces_ids))	
						for id in self.on_same_surfaces_ids:
							self.on_same_surfaces.append(self.id2node[id])
				
				if r == 'HOLD':
					# self.grabbed_objects.append(y)
					self.grabbed_objects = self.id2node[y]
				if r == 'CLOSE':
					self.reachable_objects.append(self.id2node[y])
				if r == 'ABOVE' and 'LANDABLE' in self.id2node[y]['properties']:
					self.landable_surfaces = self.id2node[y]

		self.unreached_objects = copy.deepcopy(obs['nodes'])
		for node in obs['nodes']:
			if node == self.grabbed_objects or node in self.reachable_objects:
				self.unreached_objects.remove(node)
			elif node['category'] == 'Rooms' or node['category'] == 'Agents' or node['category'] == 'Floor' or "HIGH_HEIGHT" in node['properties'] or 'ON_HIGH_SURFACE' in node['properties']:
				self.unreached_objects.remove(node)  #The idea here is to find the places that the robotic dog has not reached, remove what it already has in its hand, remove what it is close to, remove the room, the floor, the agent itself, the high surface and what is on the high surface

		self.doors = []
		self.next_rooms = []
		self.doors = [x for x in obs['nodes'] if x['class_name'] == 'door']
		for door in self.doors:
			for edge in self.init_graph['edges']:
				if edge['relation_type'] == "LEADING TO" and edge['from_id'] == door['id'] and edge['to_id'] != self.current_room["id"]:
						self.next_rooms.append([self.init_id2node[edge['to_id']], door])

		info = {'graph': obs,
				"obs": {	
						 "agent_class": self.agent_node["class_name"],
						 "agent_id":self.agent_node["id"],
						 "grabbed_objects": self.grabbed_objects,
						 "reachable_objects": self.reachable_objects,
						 "on_surfaces": self.on_surfaces,
						 "landable_surfaces": self.landable_surfaces,
						 "doors": self.doors,
						 "next_rooms": self.next_rooms,
						 "objects_on_the_same_surfaces": self.on_same_surfaces,
						 "satisfied": self.satisfied,
						 "current_room": self.current_room['class_name'],
						},
				}

		raw_llm_output, a_info = self.LLM_plan() # Renamed message to raw_llm_output for clarity

		# --- Start: Parse LLM JSON output ---
		feedback_json = None
		plan = None
		llm_message = "" # Default message if parsing fails

		try:
			# Attempt to parse the raw output as JSON
			feedback_json = json.loads(raw_llm_output)
			# Extract planned action and reasoning message
			plan = feedback_json.get('action_attempted')
			llm_message = feedback_json.get('message', raw_llm_output) # Use raw output as fallback message
			
			# Basic validation (check if required fields exist, though schema is stricter)
			if not isinstance(feedback_json, dict) or 'action_attempted' not in feedback_json or 'message' not in feedback_json:
				print(f"WARNING: LLM JSON output missing required fields. Raw: {raw_llm_output}")
				raise json.JSONDecodeError("Required JSON fields missing", raw_llm_output, 0)

		except json.JSONDecodeError as e:
			print(f"ERROR: Failed to parse LLM output as JSON: {e}")
			print(f"LLM Raw Output was: {raw_llm_output}")
			# Create a fallback error JSON object
			feedback_json = {
				"status": "error_llm_parse",
				"message": f"LLM output was not valid JSON. Error: {e}. Raw output: {raw_llm_output}",
				"failure_reason_code": "LLM_OUTPUT_UNPARSEABLE",
				"action_attempted": None,
				"key_observations": None,
				"metrics": None
			}
			plan = None # No valid plan if JSON parsing failed
			llm_message = feedback_json["message"]

		if plan is None and feedback_json.get("status") != "error_llm_parse": # Check if LLM genuinely planned nothing
			print("LLM explicitly planned no action (action_attempted is null or empty).")
			# Ensure feedback_json reflects no action was planned if it wasn't an error
			if feedback_json:
				feedback_json['action_attempted'] = None


		# --- End: Parse LLM JSON output ---

		# Prepare the old 'info' dict potentially for logging or debugging, but it's less critical now
		a_info.update({"steps": self.steps}) # Keep step count
		info.update({"LLM_raw_output": raw_llm_output, "LLM_parsed_message": llm_message, "LLM_a_info": a_info}) # Store raw/parsed info

		# Return the planned action and the full parsed feedback JSON object
		# The orchestrator (LLM_oracle.py) will execute 'plan' and then fill the
		# execution-related fields ('status', 'key_observations', etc.) in 'feedback_json'
		# before saving it to history.
		return plan, feedback_json # Return plan and the JSON object
