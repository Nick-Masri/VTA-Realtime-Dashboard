function [gridPowAvail] = initGridAvailability(fileName, numDays)

% This function sets the power available from the grid. The output of this
% function is normalized such that the maximum power available from the
% grid is 1 kWh. 
%       time increment: 15 minutes
%       time duration: 3 days

% Get data from Excel Doc
gridPowAvail = zeros(1,96);
gridData = readmatrix(fileName,'Range','B7:KC7');
for i = 1:96
    gridPowAvail(1,i) = 1000*gridData(1,3*i);
end

% Normalize to 1kWh maximum available
maxAvail = max(gridPowAvail);
gridPowAvail = gridPowAvail/maxAvail;

% Extend list to proper number of days
gridPow_init = gridPowAvail;
for d = 1:numDays-1
    gridPowAvail = [gridPowAvail, gridPow_init]; %#ok<AGROW>
end

end