import yaml
import subprocess
import pandas as pd
import time

# Load all routes from allRoutes.xlsx
df = pd.read_excel('allRoutes.xlsx')
df = df[df.incompatible == False]

# Modify the config file each time and run main.py with the new config
for i in range(40):

    #############
    # first run
    #############
    # Load the initial configuration
    with open('config.yml', 'r') as f:
        config = yaml.safe_load(f)

    # Change the filename being saved
    config['filename'] = f'flex_test {i}'

    # Randomly sample 10 routes without repeats
    print(df['routeNum'].sample(10).to_list())
    config['routes'] = df['routeNum'].sample(10).to_list()

    # Make the first run dynamic
    config['runType'] = 'dynamic'

    # Save the modified configuration
    with open('config.yml', 'w') as f:
        yaml.safe_dump(config, f)

    # Call main.py with a timeout of 3 minutes
    start_time = time.time()
    proc = subprocess.Popen(['python3', 'main.py'], stdout=subprocess.PIPE)
    try:
        outs, errs = proc.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        print(f"First run of main.py for iteration {i} timed out after 3 minutes")
        continue

    results = pd.read_csv('results.csv')

    # only run the second run if the first was successful
    if not results[results['case_name'] == f'flex_test {i}'].empty:
        #############
        # second run
        #############
        # Load the initial configuration
        with open('config.yml', 'r') as f:
            config = yaml.safe_load(f)

        # Make the second run static
        config['runType'] = 'static'

        # Save the modified configuration
        with open('config.yml', 'w') as f:
            yaml.safe_dump(config, f)

        # Call main.py
        subprocess.call(['python3', 'main.py'])
