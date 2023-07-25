function [gridPowPrice] = initGridPricingModel(numDays)

% This function sets the price per kWh of grid electricity
%       time increment: 15 minutes

% Assume summer weekday pricing
%   Peak:       .59002 dollars per kwh     12:00 - 18:00
%   Partial:    .29319 dollars per kwh     08:30 - 12:00;   18:00 - 21:30
%   Off Peak:   .22161 dollars per kwh     00:00 - 8:30;    21:30 - 24:00

% Create list of prices for single day
gridPowPrice = zeros(1,96);
for t = 1:96
    minutes = 15*t;
    if ((minutes > 12*60) && (minutes <= 18*60))
        gridPowPrice(t) = .59002;
    elseif (((minutes > 8.5*60) && (minutes <= 12*60)) || ((minutes > 18*60) && (minutes <= 21.5*60)))
        gridPowPrice(t) = .29319;
    else
        gridPowPrice(t) = .22161;
    end
end

% Extend list to proper number of days
gridPow_init = gridPowPrice;
for d = 1:numDays-1
    gridPowPrice = [gridPowPrice, gridPow_init]; %#ok<AGROW>
end


end

