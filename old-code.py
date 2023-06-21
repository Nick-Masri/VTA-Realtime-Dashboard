
##########################################################
# Tab 3: Assignment Optimization
##########################################################
# with tab3:
#     if option == ' Safe Prob.':
#         probabilities = prob_data[['coach', 'block', 'safe_prob']]
#     elif option == 'Overall Prob.':
#         probabilities = prob_data[['coach', 'block', 'prob']]
#     else:
#         probabilities = prob_data[['coach', 'block', 'safe_prob']]
#
#     probabilities['coach'] = probabilities['coach'].astype(str)
#     probabilities['block'] = probabilities['block'].astype(str)
#     probabilities = probabilities.set_index(['coach', 'block'])
#
#     with st.form("Config"):
#         st.markdown("### Recommended Assignments (for current SOC): ")
#
#         option = st.selectbox(
#             'What probability completion method do you want to use?',
#             ('Safe Prob.', 'Overall Prob.'))
#
#         values = st.slider(
#             'Probability threshold needed to be assigned (default of 95%)',
#             0.0, 99.0, 95.0)
#
#         submitted = st.form_submit_button("Recalculate with Selections")
#
#         if submitted:
#             values = values * .01
#             assignments = solve(probabilities, ebec_input, prob_data, threshold=values)
#         else:
#             assignments = solve(probabilities, ebec_input, prob_data)
#
#         assignments = assignments.reset_index()
#         assignments = assignments.merge(prob_data, left_on=['index', 'Block'], right_on=['coach', 'block'], how='left')
#         assignments = assignments.set_index('index')[['Block', option]].sort_index()
#         if assignments.shape[0] > 0:
#             st.dataframe(assignments, use_container_width=True)
#         else:
#             st.write("No blocks meet the threshold")

# TODO: add probability slider
# TODO: add checkbox to select which buses
# TODO: update to include distances as well
# TODO: Highlight input and output based on probability
# TODO: Reformat input code to tell a better story

# with st.expander("See explanation"): st.write("This code solves an optimization problem to determine the best
# assignment of electric buses to different blocks, based on the distance each bus needs to travel and the
# probability that each bus will have a certain efficiency level. It does this by creating a mathematical model
# and adding constraints to ensure that each bus and block is assigned to only one coach or block, respectively.
# The code then solves the optimization problem and returns the solutions as a table of values.")
#
# ##########################################################
# # Tab 4: Charging Optimization (realtime)
# ##########################################################
# #
# with tab4:
#
#     with st.form("chargeopt-form"):
#         ########################
#         # Vehicles
#         ########################
#
#         st.write("# Vehicles")
#         vehicles = output[['Vehicle', 'SOC (%)', 'Last Online']]
#         vehicles = vehicles.sort_index(ascending=True)
#
#         # Set up the grid options
#         gb = GridOptionsBuilder.from_dataframe(vehicles)
#         gb.configure_default_column(groupable=False, value=True, enableRowGroup=True,
#                                     aggFunc='sum', editable=True, min_column_width=1)
#         gb.configure_selection('multiple', use_checkbox=True, pre_selected_rows=[i+1 for i in range(len(vehicles))])
#         gb.configure_grid_options(domLayout='normal')
#
#         # Build the grid options
#         gridOptions = gb.build()
#
#         return_mode = DataReturnMode.__members__['FILTERED_AND_SORTED']
#
#         vehicleResponse = AgGrid(vehicles, gridOptions=gridOptions,
#                                  width='100%')
#
#         ########################
#         # Blocks
#         ########################
#
#         st.write("# Blocks")
#         data = pd.read_excel('allRoutes.xlsx')
#
#         # Set up the grid options
#         gb = GridOptionsBuilder.from_dataframe(data)
#         gb.configure_default_column(groupable=False, value=True, enableRowGroup=True,
#                                     aggFunc='sum', editable=True, min_column_width=1)
#         gb.configure_selection('multiple', use_checkbox=True)
#         gb.configure_grid_options(domLayout='normal')
#
#         # Build the grid options
#         gridOptions = gb.build()
#
#         # Display the AgGrid
#         selected_rows = AgGrid(data,
#                                gridOptions=gridOptions,
#                                width='100%', )
#
#         # Get the list of selected checkboxes
#         if selected_rows is not None:
#             selected_checkboxes = selected_rows['selected_rows']
#             st.write(selected_checkboxes)
#             # optim(selected_checkboxes)
#
#         # Submit
#         submitted = st.form_submit_button("Recalculate with Selections")
#
# #     with st.form("Charging Optimization"):
# #         st.write("Make assignments and charging decisions")
# #
# #         values = st.slider(
# #             'Probability threshold needed to be assigned (default of 95%)',
# #             0.0, 99.0, 95.0)
# #
# #         option = st.selectbox(
# #             'What Probability do you want to use?',
# #             ('Safe Prob.', 'Overall Prob.'))
# #
# #         st.form_submit_button("Recalculate with Selections")
# #         realtime_input = output[['SOC (%)']]
# #         chargeRealtime(realtime_input)
#
# # TODO: add probability slider in code
# # TODO: add checkbox to select which buses
# # TODO: output probability of final solution
# # TODO: update to include distances as well
#
# ##########################################################
# # Tab 5: Display Config
# ##########################################################
# if config['display_config']:
#     with tab5:
#         st.write("Current Config Settings")
#
#         # display json
#         st.json(config_json)
#

# ##########################################################
# # Tab 6: AgGrid Test
# ##########################################################
# with tab6:
#     def optim(selected_checkboxes):
#         # Your code to optimize based on selected checkboxes goes here
#         pass
#
#
#     data = pd.read_excel('allRoutes.xlsx')
#     st.write("AgGrid Test")
#
#     # Set up the grid options
#     gb = GridOptionsBuilder.from_dataframe(data)
#     gb.configure_default_column(groupable=True, value=True, enableRowGroup=True, aggFunc='sum', editable=True)
#     gb.configure_selection('multiple', use_checkbox=True)
#     gb.configure_grid_options(domLayout='normal')
#
#     # Build the grid options
#     gridOptions = gb.build()
#
#     # Display the AgGrid
#     selected_rows = AgGrid(data, gridOptions=gridOptions, height=400, width='100%')
#
#     # Get the list of selected checkboxes
#     if selected_rows is not None:
#         selected_checkboxes = selected_rows['selected_rows']
#         optim(selected_checkboxes)
