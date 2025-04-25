
import copy
import numpy as np
from tqdm import tqdm
import time
import json
from openai import OpenAIError,OpenAI
import backoff
import traceback

# @ray.remote
class ArenaMP(object):
    def __init__(self, environment_fn, agent_fn, args , run_predefined_actions=False):
        # run_predefined_actions is a parameter that you can use predefined_actions.json to strictly set the agents' actions instead of using algorithm to calculate the action.
        
        self.env_fn = environment_fn
        self.agents = agent_fn
        self.args = args
        self.num_agents = len(agent_fn)
        self.task_goal = None
        self.record_dir = f'./log/{args.env}.txt'
        self.debug = args.debug
        print("Init Env")
        self.env = environment_fn()
        self.run_predefined_actions = run_predefined_actions

        self.oracle_prompt_path = args.oracle_prompt_path
        self.quadrotor_prompt_path = args.quadrotor_prompt_path
        self.robot_dog_prompt_path = args.robot_dog_prompt_path
        self.robot_arm_prompt_path = args.robot_arm_prompt_path

        self.dialogue_history = ""
        self.total_dialogue_history = []
        self.chat = True
        self.source = args.source
        self.lm_id = args.lm_id
        # self.lm_id = 'gpt-3.5-turbo-1106'
        self.device = None
        self.sampling_parameters = None
        self.total_cost = 0

        self.last_done = False
        self.last_task_results = None
        self.last_satisfied = None
        self.last_unsatisfied = None
        self.costdict = {}
       

        if self.source == 'openai':
            api_key = args.api_key # your openai api key
            organization=args.organization # your openai organization

            client = OpenAI(api_key = api_key, organization=organization)
            if self.chat:
                self.sampling_params = {
                    "max_tokens": args.max_tokens,
                    "temperature": args.t,
                    # "top_p": args.top_p,
                    "n": args.n
                }

        def lm_engine( source, lm_id, device):

            @backoff.on_exception(backoff.expo, OpenAIError)
            def _generate(prompt, sampling_params):
                usage = 0
                if source == 'openai':
                    try:
                        if self.chat:
                            prompt.insert(0,{"role":"system", "content":"You are a helper assistant."})
                            response = client.chat.completions.create(
                                model=lm_id, messages=prompt, **sampling_params
                            )
                            if self.debug:
                                with open(f"./chat_raw.json", 'a') as f:
                                    f.write(json.dumps(response, indent=4))
                                    f.write('\n')
                            generated_samples = [response.choices[i].message.content for i in
                                                    range(sampling_params['n'])]
                            if 'gpt-4-0125-preview' in self.lm_id:
                                usage = response.usage.prompt_tokens * 0.01 / 1000 + response.usage.completion_tokens * 0.03 / 1000
                            elif 'gpt-3.5-turbo-1106' in self.lm_id:
                                usage = response.usage.prompt_tokens * 0.0015 / 1000 + response.usage.completion_tokens * 0.002 / 1000
                        # mean_log_probs = [np.mean(response['choices'][i]['logprobs']['token_logprobs']) for i in
                        # 				  range(sampling_params['n'])]
                        else:
                            raise ValueError(f"{lm_id} not available!")
                    except OpenAIError as e:
                        print(e)
                        raise e

                else:
                    raise ValueError("invalid source")
                return generated_samples, usage 
            
            return _generate

        self.generator = lm_engine(self.source, self.lm_id, self.device)

    def get_actions(self, obs, chat_agent_info):

        for id, agent in enumerate(self.agents):
            if agent.agent_node["id"] == chat_agent_info["id"]:

                action, message, info = agent.get_action(obs[id], chat_agent_info, self.env.task_goal)

        return action, message, info

    def agent_obs2text(self, observation, agent_id):
        text = ""
        observation = observation[agent_id]
       
        id2node = {node['id']: node for node in observation["nodes"]}
        agent_class = id2node[int(self.env.id_name_dict[agent_id][1])]["class_name"]
        with_quadrotor_id = None
        for node in observation["nodes"]:
            if node["category"] == "Agents" and self.env.id_name_dict[agent_id][1] == node["id"]:
                # agent_node = node
                text += "I am <" + node["class_name"] +">(" + str(node["id"]) + "). "   
                if len(node['states']) != 0:
                    states = ', '.join(node['states'])
                    text += "Now my state is: " + states + ". "
                for edge in observation["edges"]:
                    if edge["from_id"] == node["id"]:
                        text += "I am " + edge["relation_type"] + " the <" + id2node[edge["to_id"]]["class_name"] + ">(" + str(edge["to_id"]) + "). "
                    if edge["relation_type"] == "WITH":
                        with_quadrotor_id = edge["to_id"]
                text += '\n'


        for node in observation["nodes"]:
            if node["category"] == "Rooms" and node["id"] == observation["agent_in_room_id"]:
                text += "Now I am in the <"+ node["class_name"] +">(" + str(node["id"]) + "). In this room, I can see : \n"
        for node in observation["nodes"]:
            if node["id"] != self.env.id_name_dict[agent_id][1] and node["category"] != "Rooms":
                text += "<" + node["class_name"] +">(" + str(node["id"]) + "). "
                if len(node['properties']) != 0:
                    properties = ', '.join(node['properties'])
                    text += "Its properties are: " + properties + ". "
                if len(node['states']) !=0 :
                    states = ', '.join(node['states'])
                    text += "Now its state is: " + states + ". \n"
                else:
                    text += '\n'
        text += "These objects have a certain position relationship with each other: \n"
        for node in observation["nodes"]:
            if node["id"] != self.env.id_name_dict[agent_id][1] and node["category"] != "Rooms":
                for edge in observation["edges"]:
                    if edge["from_id"] == node["id"]: 
                    # if edge["from_id"] == node["id"] and edge["relation_type"] != "WITH" : #WITH is exclusive to quadrotor and basket
                        if edge["from_id"] == with_quadrotor_id and agent_class == 'quadrotor':
                            text += "The <" + node["class_name"] +">(" + str(node["id"]) + ") is with me LAND " + edge["relation_type"] + " the <" + id2node[edge["to_id"]]["class_name"] + ">(" + str(edge["to_id"]) + "). \n"
                        elif edge["relation_type"] == "LEADING TO":
                            text += "The <" + node["class_name"] +">(" + str(node["id"]) + ") is " + edge["relation_type"] + " the <" + id2node[edge["to_id"]]["class_name"] + ">(" + str(edge["to_id"]) + "). \n"
                        else:
                            text += "The <" + node["class_name"] +">(" + str(node["id"]) + ") is " + edge["relation_type"] + " the <" + id2node[edge["to_id"]]["class_name"] + ">(" + str(edge["to_id"]) + "). \n"
        for edge in observation["edges"]:
            if edge["relation_type"] == "WITH" and agent_class == 'quadrotor':
                in_basket = False
                text += "I have a <" + id2node[edge["to_id"]]["class_name"] + ">(" + str(edge["to_id"]) + ") with me. " 
                for edges in observation["edges"]:
                    if edges["to_id"] == edge["to_id"] and edges["relation_type"] == "INSIDE" :
                        text += "<" + id2node[edges["from_id"]]["class_name"] + ">("+ str(edges["from_id"]) + ") is in my <" + id2node[edge["to_id"]]["class_name"] + ">(" + str(edge["to_id"]) + "). \n"
                        in_basket = True    
                if in_basket == False:
                    text += "But nothing is in my <" + id2node[edge["to_id"]]["class_name"] + ">(" + str(edge["to_id"]) + "). \n"
            if edge["relation_type"] == "HOLD" and agent_class != 'quadrotor':
                text += "I am holding a <" + id2node[edge["to_id"]]["class_name"] + ">(" + str(edge["to_id"]) + ") in my hand. \n"    
        # print(text)
        return text
    
    def write_log_to_file(self,log_message, file_name = None):
        file_name = self.record_dir
        with open(file_name, 'a') as file:  
            file.write(log_message + '\n')  

    def step(self):
        if self.env.steps == 0:
            pass

        obs = self.env.get_observations()
        id_name_dict = self.env.id_name_dict

        obs2text = ''
        for i in range(self.num_agents):
            obs2text += self.agent_obs2text(obs, i) + '\n'

        oracle_prompt = self.oracle_prompt_path 
        with open(oracle_prompt, 'r') as f:
            oracle_prompt = f.read()
        oracle_prompt = oracle_prompt.replace('#AGENT_OBSERVATIONS#', obs2text)
        oracle_prompt = oracle_prompt.replace('#TASK_GOAL#', self.env.goal_instruction)
        oracle_prompt = oracle_prompt.replace('#NUMBER_AGENTS#', str(self.env.num_agent))
        oracle_prompt = oracle_prompt.replace('#DIALOGUE_HISTORY#', self.dialogue_history)  
        print(self.dialogue_history)
      

        print('@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@')
        print((f"@@@@@@@@@@@@@@@@@@@@@@@@ Task_ID: {self.env.task_id} @@@@@@@@@@@"))
        print(f"$$$$$$$$$$$$$$$$$$$$$$$ Step:{self.env.steps} $$$$$$$$$$$$$$$$$$$$$$$")
        print(self.env.goal_instruction)
              
        chat_prompt = [{"role": "user", "content": oracle_prompt}]
        outputs, usage = self.generator(chat_prompt, self.sampling_params)
        self.total_cost += usage
        message = outputs[0]

        self.write_log_to_file(f"@@@@@@@@@@@@@@@@@@@@@@@ Task_ID: {self.env.task_id} @@@@@@@@@@@")
        self.write_log_to_file(f"$$$$$$$$$$$$$$$$$$$$$$$ Step:{self.env.steps} $$$$$$$$$$$$$$$$$$$$$$$")
        self.write_log_to_file(f'''*******************************************************************************************
                               TASK_GOAL: {self.env.goal_instruction}
                               ''')
        self.write_log_to_file("OBSERVATIONS: \n" + obs2text)
        self.write_log_to_file("Oracle: " + message)

        self.total_dialogue_history.append( "Oracle: " + message)
        extract_prompt = message + '\n' + 'Extract from the above paragraph the content of the format "Hello <class name>(id): message.". Then output the contents of this section. Be careful not to output any superfluous content, exactly in the format given. If the above paragraph is not exactly formatted as "Hello <class name>(id): #message#.", output similar content in this format. As an example, the output might read: "Hello <robot dog>(0): please movetowards the <door>(1), and then open the <door>(1)". If this format does not appear in the preceding text, please summarize the above content into this format for output. To emphasize once again, the names of all objects and agent robots must be enclosed in <>, and the (id) must not be omitted. Class name missing <> and (id) should be completed with these elements. Please strictly follow this format in the output content.' 
        chat_prompt = [{"role": "user", "content": extract_prompt}]
        outputs, usage = self.generator(chat_prompt , self.sampling_params)
        self.total_cost += usage
        message = outputs[0]
        self.subgoal = message

        self.write_log_to_file("Oracle: " + message)
        
        if self.debug:
        # input('wait a minute!')
            print(f"message_oracle_prompt:\n{oracle_prompt}")
            print('\n')
            print(f"message_oracle_outputs:\n{message}")
        try:
            start_class_name = message.find('<') + 1  
            end_class_name = message.find('>')        
            start_id = message.find('(') + 1          
            end_id = message.find(')')                

            # extract class_name and real_id
            class_name = message[start_class_name:end_class_name]
            real_id = int(message[start_id:end_id])
            id  = [key for key, value in id_name_dict.items() if value[1] == real_id]
            agent_obs = self.agent_obs2text(obs, id[0])

            if class_name == 'quadrotor':
                prompt_path = self.quadrotor_prompt_path
            elif class_name == 'robot dog' or class_name == 'robot_dog':
                prompt_path = self.robot_dog_prompt_path
            elif class_name == 'robot arm' or class_name == 'robot_arm':
                prompt_path = self.robot_arm_prompt_path

            chat_agent_info = {"class_name": class_name,
                            "id": real_id,
                            "observation": agent_obs,
                            "instruction": message,
                            "prompt_path": prompt_path
                            }

            feedback_json = None # Initialize feedback_json
            agent_action, feedback_json = self.get_actions(obs, chat_agent_info) # Get action and feedback dict

            # Extract message for logging/history, handle potential None feedback_json if get_actions failed internally (should not happen with new logic)
            agent_log_message = feedback_json.get('message', 'Error: Could not retrieve feedback message.') if feedback_json else 'Error: feedback_json is None.'
            # Log the message part of the feedback
            self.write_log_to_file(f"<{class_name}>({real_id}) - Planned Action: {agent_action}")
            self.write_log_to_file(f"<{class_name}>({real_id}) - Feedback Message: {agent_log_message}")
            if self.debug:
                 self.write_log_to_file(f"<{class_name}>({real_id}) - Full Feedback JSON (Initial): {json.dumps(feedback_json, indent=2)}")


            # --- Cost calculation (Assuming agent_info is no longer returned or needed here) ---
            # self.costdict =  self.update_dict(f"<{class_name}>({real_id})", agent_info["LLM"]["cost"], self.costdict) # Needs update if cost info source changes
            # self.write_log_to_file(f"COST1:{self.total_cost}!!!!!") # Assuming total_cost is updated elsewhere (e.g., in self.generator)
            # self.write_log_to_file(str(self.costdict))
            # self.write_log_to_file(f"COST2:{sum(self.costdict.values())}!!!!!")
            # self.write_log_to_file(f'Total Cost (Placeholder): {self.total_cost + sum(self.costdict.values())}') # Placeholder, cost calculation might need rework
            self.write_log_to_file('$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$ ')


            # --- Update dialogue history with the structured feedback ---
            current_feedback_entry = f"<{class_name}>({real_id}):\n{json.dumps(feedback_json, indent=2)}" if feedback_json else f"<{class_name}>({real_id}): [Error processing feedback]"
            self.total_dialogue_history.append(current_feedback_entry) # Append initial feedback (status will be updated after execution)
            # Note: dialogue_history used in the prompt will be updated later, after execution status is known

        except Exception as e:
            # This exception handles errors *before* calling env.step (e.g., parsing Oracle message, calling get_actions)
            print(f"An error occurred before action execution: {e}")
            traceback.print_exc()
            error_info = traceback.format_exc()
            self.write_log_to_file(f"An error occurred before action execution: {e}")
            self.write_log_to_file(error_info + '\n\n')
            agent_action = None # No action planned due to error
            # Create an error feedback JSON to record in history
            feedback_json = {
                "status": "error_oracle_phase",
                "message": f"Oracle phase error before execution: {e}. Traceback: {error_info}",
                "failure_reason_code": "ORACLE_PRE_EXECUTION_ERROR",
                "action_attempted": None,
                "key_observations": None,
                "metrics": None
            }
            # Don't update total_dialogue_history here, let the post-action logic handle it


        # --- Execute Action and Update Feedback ---
        execution_successful = False # Flag to track if env.step succeeded
        if agent_action is None:
            # Handle case where no action was planned (either LLM decided so, or error occurred)
            print("No action to execute.")
            # Use the feedback_json generated above (either from agent or error handling)
            # Ensure status reflects why no action was taken if feedback_json isn't already an error status
            if feedback_json and feedback_json.get('status') not in ['error_llm_parse', 'error_oracle_phase']:
                 feedback_json['status'] = 'no_action_planned' # Or keep agent's original status if it explained why (e.g., already done)

            # Need to maintain state consistency from the previous step
            done = self.last_done
            task_results = self.last_task_results
            satisfied = self.last_satisfied
            unsatisfied = self.last_unsatisfied
            # Increment step count manually if no action is taken? Original code did this.
            self.env.steps += 1 # Keep consistency with original logic
        else:
            # Execute the planned action
            try:
                done, task_results, satisfied, unsatisfied, steps = self.env.step(class_name, real_id, agent_action, self.task_goal)
                self.last_done = done
                self.last_task_results = task_results
                self.last_satisfied = satisfied
                self.last_unsatisfied = unsatisfied
                execution_successful = True

                # Update feedback_json status based on execution outcome
                if feedback_json: # Should always exist unless primary try block failed catastrophically
                    if done and task_results: # Assuming task_results=True means success
                        feedback_json['status'] = 'success' # Overall task success
                    elif feedback_json.get('status') != 'failure': # If agent didn't already report failure
                         feedback_json['status'] = 'partial_success' # Step executed, task not done

            except Exception as e:
                print(f"Exception occurred when performing action: {agent_action}, Error: {e}")
                traceback.print_exc()
                error_info = traceback.format_exc()
                # Update feedback_json to reflect execution error
                if feedback_json:
                    feedback_json['status'] = 'error_execution'
                    feedback_json['failure_reason_code'] = 'EXECUTION_EXCEPTION'
                    # Append execution error details to the message
                    original_message = feedback_json.get('message', '')
                    feedback_json['message'] = f"{original_message}\n\nEXECUTION FAILED: {e}\n{error_info}"
                else: # Should not happen, but as a fallback
                     feedback_json = {
                        "status": "error_execution",
                        "message": f"Action execution failed: {e}. Traceback: {error_info}",
                        "failure_reason_code": "EXECUTION_EXCEPTION",
                        "action_attempted": agent_action,
                        "key_observations": None,
                        "metrics": None
                    }
                # Need to maintain state from last successful step
                done = self.last_done
                task_results = self.last_task_results
                satisfied = self.last_satisfied
                unsatisfied = self.last_unsatisfied

        # --- Finalize Dialogue History for next step ---
        # Update the last entry in total_dialogue_history with the potentially modified feedback_json
        final_feedback_entry = f"<{class_name}>({real_id}):\n{json.dumps(feedback_json, indent=2)}" if feedback_json else f"<{class_name}>({real_id}): [Error processing final feedback]"
        if self.total_dialogue_history: #
             self.total_dialogue_history[-1] = final_feedback_entry # Replace the initial entry with the final one including execution status
        else: # Should not happen based on code flow, but safeguard
             self.total_dialogue_history.append(final_feedback_entry)


        # Update the dialogue history snippet for the next prompt
        numbered_list = [f"[{i + 1}]、{item}" for i, item in enumerate(self.total_dialogue_history)]
        self.dialogue_history = '\n'.join(numbered_list[-10:]) # Use the updated history

        self.write_log_to_file(f'\nFINAL DIALOGUE_HISTORY SNIPPET (for next prompt):\n{self.dialogue_history}')
        steps = self.env.steps

        # The agent_message returned might be less useful now, maybe return the final feedback_json instead?
        # Keeping original return signature for now to minimize downstream changes, but agent_message is just the parsed LLM message.
        # Returning final 'feedback_json' itself might be better long-term.
        final_llm_message = feedback_json.get('message', '') if feedback_json else '[Error retrieving final message]'

        return done, task_results, satisfied, unsatisfied, id[0] if 'id' in locals() and id else None, agent_action, final_llm_message, steps # Return agent_id correctly


    def run(self):
        
        self.task_goal = copy.deepcopy(self.env.task_goal)
        saved_info = []

        success = False
        while True:
            
            done, task_results, satisfied, unsatisfied, id, agent_action, agent_message,steps  = self.step()
            saved_info.append({'task_id': self.env.task_id,
                      'env_id': self.env.env_id,
                      'task_name': self.env.task_name,
                      'gt_steps': self.env.ground_truth_step_num,
                      'task_goal': self.task_goal,
                      'goal_instruction': self.env.goal_instruction,
                      'step': steps,
                      'subgoal': self.subgoal, # This is the Oracle's command message
                      'agent_id': id, # Use the returned agent_id from step()
                      'action': agent_action, # The actual action executed
                      'agent_message': agent_message, # The message field from the agent's final feedback JSON
                      'satisfied': satisfied,
                      'unsatisfied': unsatisfied,
                      'env_graph': self.env.graph, 
                    })
           
            success = done
      
            max_setp = 2 * self.env.ground_truth_step_num
            if self.env.steps > max_setp:
                print("---------------------------")
                print("The task failed, exceeding 2 times the number of GT steps")
                print(f"Whether steps in gt*2+1 are successful:{done}")
                print(f" setps: {steps}")
                print("---------------------------")
                self.write_log_to_file(f'''---------------------------
                                       The task failed, exceeding 2 times the number of GT steps
                                       Whether steps in gt*2+1 are successful:{done}
                                       setps: {steps}
                                       ---------------------------
                                       ''')
            
                success = False
                break
            
            if success:
                
                self.write_log_to_file(f'''-------------------------------------
                                            success!
                                            setps: {steps}
                                            --------------------------------
                                            ''')
                break

        end_time = time.time() # Record end time
        total_duration = end_time - start_time
        final_total_cost = self.total_cost + self.total_agent_cost

        log_summary = f"""
        ================ TASK SUMMARY ================
        Task ID: {self.env.task_id}
        Success: {success}
        Total Steps: {final_steps} (GT Steps: {self.env.ground_truth_step_num})
        Total Execution Time: {total_duration:.2f} seconds
        Total Oracle API Cost: {self.total_cost:.6f}
        Total Agent API Cost: {self.total_agent_cost:.6f}
        Total Overall API Cost: {final_total_cost:.6f}
        ============================================
        """
        print(log_summary)
        self.write_log_to_file(log_summary)

        # Update the last entry in saved_info with final metrics
        if saved_info:
            saved_info[-1]['is_finished'] = success
            saved_info[-1]['cumulative_cost'] = final_total_cost
            saved_info[-1]['execution_duration_seconds'] = total_duration


        return success, final_steps, saved_info

    def update_dict(self,key, value, my_dict):

        my_dict[key] = value
        return my_dict
