function [departure, arrival, eRoute, report] = initRoutesDynamically(routeNums, numDays, eB_max, pCB_max)

% This function extracts the information that constrains the charging and
% discharging of the bus fleet. The user selects the routes they wish to
% serve, and this function schedules a bus to run each route every day. 
%
% This function also checks that routes will not violate a few conditions
% that would lead for the model to immediately become infeasible - being
% above the operating ranges for the busses, returning too close to the end
% of the optimization horizon.
%
% The user chooses the list of routes, and informs the function of a few
% key parameters (maximum range of busses, power rating of chargers, etc.)
%       time increment: 15 minutes


% Read in all the data
routeData = readmatrix('allRoutes.xlsx','Range','B4:E286' );

% Determine the number of busses 
numRoutes = size(routeNums,2);

% Intialize arrays for bus scheduling
nRoutes = zeros(numRoutes,1) + numDays;
eRoute = zeros(numRoutes,1);
routeReturn = zeros(numRoutes,1);
nRunning = zeros(1,4*24);

departure = zeros(numRoutes, 1);
arrival = zeros(numRoutes, 1);

% For each route we have selected:
%   set the bus as unavailable for the duration of the route
%   determine how much to discharge the bus by when it returns
for i = 1:numRoutes
    % Get route information
    r = routeNums(i);
    tDepart = routeData(r,2);
    tReturn = routeData(r,3);
    distance = routeData(r,4);
    tRoute = tDepart:tReturn;
    routeReturn(i) = tReturn;
    
    departure(i) = tDepart;
    arrival(i) = tReturn;
    
    % Calculate energy of route
%     kwhPerMile = 2;
    kwhPerMile = 2; % top 10 occuring operators
    routeEnergy = distance * kwhPerMile;
    eRoute(i) = routeEnergy;
    

    % Track how many routes run at each time
    nRunning(tDepart:tReturn) = nRunning(tDepart:tReturn) + 1;
end

% Check for route energy out of bounds, route returning too late
routeOutOfRange = false;
routeLateReturn = false;
for i = 1:numRoutes
    if eRoute(i) >= eB_max
        routeOutOfRange = true;
    end
    timeToCharge = (1/.94)*60*eRoute(i)/pCB_max;
    indicesToCharge = ceil(timeToCharge/15);
    if indicesToCharge >= (arrival(i)+96 - departure(i))
        routeLateReturn = true;
    end
end

% Return report on infesible route
report = 'All Clear';
if routeLateReturn && routeOutOfRange
    report = 'Multiple Route Issues';
elseif routeLateReturn
    report = 'Route Returns Too Late';
elseif routeOutOfRange
    report = 'Route Out Of Range';
end

% Optional: graph routes running per time
% plot(1:96, nRunning) 
% title('Number of Routes Running Per ToD')
% xlabel('Time (h)')
% ylabel('Routes in Operation')

end

