function [solarPowAvail] = initSolarPowModel(season, numDays, mornings, noons, nights)

% This function determines how much solar power is available for use at any
% given time increment. The user may choose if clouds roll during the
% morning, midday, or afternoon periods of each day. The user may also
% choose between summer or winter solar production. 
%       time increment: 15 minutes
%       time duration: 3 days

% SOLAR GENERATION PARAMETERS 
AZ_ANG_ARRAY = 180;      % PV solar panel array azimuth angle                degrees
TILT_ANG_ARRAY = 30;     % PV solar panel array tilt angle                   degrees
LAT = 37.385;            % observer latitude                                 degrees
LONG_SM = 120;           % longitude of standard meridian time zone          degrees
LONG_LOC = 121.8863;     % observer local longitude                          degrees
EFF_ARRAY = .15;         % PV solar panel array efficiency                   percent
DC_MW_rating = 3.75;     % DC power rating of PV solar panel @ STC           MW
STC_solar_irr = 1000;    % Solar irradiation on PV solar panel @ STC         W / m^2
SOIL_LOSS = .02;         % Array system losses due to foriegn matter         %
SHADING_LOSS = 0;        % Array system losses due to shadows                %
SNOW_LOSS = 0;           % Array system losses due to snow                   %
MISMATCH_LOSS = .02;     % Array system losses due to imperfections          %
WIRING_LOSS = .02;       % Array system losses due to resistance             %
CONNECTION_LOSS = .005;  % Array system losses due to electric connectors    %
DEGRADATION_LOSS = .015; % Array system losses due to light degradation      %
NAMEPLATE_LOSS = .01;    % Array system losses due to nameplate inaccuracy   %
AGE_LOSS = 0;            % Array system losses due to weathering             %
AVAIL_LOSS = .03;        % Array system losses due to system shutdowns       %
INVERTER_EFF = .95;      % DC to AC Inverter Efficiency                      %           
CLOUDY_EFF = .2;         % Percent output on cloudy days                     %

% AVAILABLE SOLAR POWER PER TIME STEP 
arrayArea = (DC_MW_rating*10^6) / (STC_solar_irr*EFF_ARRAY);                % m^2
performanceRatio = (1-SOIL_LOSS)*(1-SHADING_LOSS)*(1-SNOW_LOSS)*(1-MISMATCH_LOSS);
performanceRatio = performanceRatio*(1-WIRING_LOSS)*(1-CONNECTION_LOSS)*(1-DEGRADATION_LOSS);
performanceRatio = performanceRatio*(1-NAMEPLATE_LOSS)*(1-AGE_LOSS)*(1-AVAIL_LOSS);

% Open Excel file containing NSRD Data 
DN_solar_irr = readmatrix('DNI_data_2015.xlsx','Sheet','DNI_data_2015','Range','G4:G17523');% Read in Direct Normal Irradiance Data for all days in a year
DH_solar_irr = readmatrix('DNI_data_2015.xlsx','Sheet','DNI_data_2015','Range','F4:F17523');% Read in Diffuse Horizontal Irradiance Data for all days in a year

% DH_solar_irr(17:25)
% size(DH_solar_irr)

% Create list of days of year and times of day
% Creates solar calculations dependent on the location of earth in orbit and earth's tilt
daysinyear = 365;
day_YR = 1:daysinyear; % day of year 
local_time = 0:0.5:23.5; % time of day in 30 minute increments 
Eqt = zeros(1,daysinyear); 
solarTime = zeros(daysinyear,length(local_time));

% Calculate declination angle of sun on each day - Based on day of year only 
declinationAng = 23.45*sind((360/365)*(284 + day_YR)); 

% Calculate Equation of Time - "Eqt" - Based on day of year only
for i = 1:daysinyear
    if day_YR(i) <= 106
        Eqt(i) = -14.2*sin((pi/111)*(day_YR(i)+7));
    elseif day_YR(i) >= 107 && day_YR(i) <= 166
        Eqt(i) = 4*sin((pi/59)*(day_YR(i)-106));
    elseif day_YR(i) >= 167 && day_YR(i) <= 246
        Eqt(i) = -6.5*sin((pi/80)*(day_YR(i)-166));  
    else 
        Eqt(i) = 16.4*sin((pi/113)*(day_YR(i)-247));
    end
end

% Calculate array irradiance angle for each half hour of each day
for i = 1:daysinyear
    for j = 1:length(local_time)
        % Calculate solar time 
        solarTime(i,j) = local_time(j) + (Eqt(i)/60) + ((LONG_SM - LONG_LOC)/15); % in hours
        % Calculate hour angle
        hourAng(i,j) = 15*(solarTime(i,j) - 12); % degrees
        % Calculate Solar Zenith Angle
        solar_zenithAng(i,j) = acosd((sind(LAT)*sind(declinationAng(i))) + (cosd(LAT)*cosd(declinationAng(i))*cosd(hourAng(i,j)))); % degrees
        % Calculate Solar Elevation Angle 
        solar_elevationAng(i,j) = asind(sind(declinationAng(i))*sind(LAT) + cosd(declinationAng(i))*cosd(hourAng(i,j))*cosd(LAT)); % degrees
        % Calculate Solar Azimuth Angle
        solar_azimuthAng(i,j) = acosd((sind(declinationAng(i))*cosd(LAT) - cosd(declinationAng(i))*cosd(hourAng(i,j))*sind(LAT))/cosd(solar_elevationAng(i,j))); % in degrees
        % Calculate Array Irradiance Angle (in 3 steps)
        arrayIrradiance_a(i,j) = cosd(solar_zenithAng(i,j))*cosd(TILT_ANG_ARRAY); % degrees
        arrayIrradiance_b(i,j) = sind(solar_zenithAng(i,j))*sind(TILT_ANG_ARRAY)*cosd(solar_azimuthAng(i,j) - AZ_ANG_ARRAY); % degrees
        arrayIrradiance_Ang_init(i,j) = acosd(arrayIrradiance_a(i,j) + arrayIrradiance_b(i,j)); % degrees       
     end
end

% Reshape 2D matrix into 1D array in which columns all all the half hours of a year in consecutive order
initVal = 0;
finVal = 17520; 
arrayIrradiance_Ang_fin = reshape(arrayIrradiance_Ang_init.',[1 finVal]);

% Solar Irradiance (DNI and DHI) that hits solar panel array normal to the surface of the solar panel in W/m^2 
arrayIrradiance_DN = DN_solar_irr.*cosd(arrayIrradiance_Ang_fin.');

size(DN_solar_irr)
size(cosd(arrayIrradiance_Ang_fin.'))

arrayIrradiance_DH = DH_solar_irr.*cosd(arrayIrradiance_Ang_fin.');
arrayIrradiance_30 = arrayIrradiance_DN + arrayIrradiance_DH;  % total irradiance incident upon solar panels
  
% Modify Solar Irradiance Array to be every 30 minutes to every 15 minutes
% to align with rest of optimization model
arrayIrradiance = repelem(arrayIrradiance_30,2);

% Calculate PV Solar Array Power Generation every 15 minutes for one year
% DC Power
PV_kW = arrayArea * performanceRatio * EFF_ARRAY * arrayIrradiance * (1/1000);

% AC Power Avaialable from solar panels
PV_kW_avail = PV_kW*INVERTER_EFF;

% Replace negative AC Power Available from solar panels with 0 
ID = PV_kW_avail < 0; % binary value of 1 when alpha is greater than 0.3
PV_kW_avail(ID) = 0;  %replace negative values with zero

% Normalize to 1kW solar generation profile
maxGen = max(PV_kW_avail);
PV_kW_avail = PV_kW_avail/maxGen;

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% SOLAR CASES %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%%% 1. Select days from winter or summer
n_JAN15 = 15;
n_JUL15 = 196; 
timesteps = 96;
if strcmp(season,'summer')
    startDay = 196;
    endDay = startDay + numDays - 1;
elseif strcmp(season,'winter')
    startDay = 15;
    endDay = startDay + numDays - 1;
end

% Generate matrix of the maximum available solar power during 3 selected winter and summer days
startTime = ((startDay-1)*timesteps)+1; 
endTime = endDay*timesteps;
PV_kW = PV_kW_avail(startTime:endTime);
PV_kW_max_reshape = reshape(PV_kW,[timesteps numDays]); % reshape into 3 columns for following for loop
PV_kW_reshape = zeros(timesteps, numDays);

%%% Modify mornings / afternoons / midday as "cloudy" or "sunny" throughout each day
% weather during morning, midday, and afternoon, respectively each day
% cloudy day power output is multiplied by the "cloudy efficiency factor" chosen in above parameters
% "malfunction" means solar panel and/or it's other parts are not working and is out of commision - power available is ZERO
morning = 1:(10*4);             % 0:00 AM - 9:45 AM
midday = ((10*4)+1):((14*4)+1); % 10:00 AM - 2:00 PM
afternoon = ((14*4)+2):96;      % 2:15 PM - 11:45 PM
PV_kW_morning = zeros(timesteps,numDays);
PV_kW_midday = zeros(timesteps,numDays);
PV_kW_afternoon = zeros(timesteps,numDays);

% Determine available Power due to different weather for morning midday and afternoon of each day
for i = 1:numDays % loop through each day
    
    % morning
    if strcmp(mornings(i),'cloudy') == 1 
        PV_kW_morning(morning,i) = PV_kW_max_reshape(morning,i)*CLOUDY_EFF;
    else 
        PV_kW_morning(morning,i) = PV_kW_max_reshape(morning,i);
    end
    % midday
    if strcmp(noons(i),'cloudy') == 1 
        PV_kW_midday(midday,i) = PV_kW_max_reshape(midday,i)*CLOUDY_EFF;
    else 
        PV_kW_midday(midday,i) = PV_kW_max_reshape(midday,i);
    end
    %afternoon
    if strcmp(nights(i),'cloudy') == 1 %
        PV_kW_afternoon(afternoon,i) = PV_kW_max_reshape(afternoon,i)*CLOUDY_EFF;
    else 
        PV_kW_afternoon(afternoon,i) = PV_kW_max_reshape(afternoon,i);
    end
     
end

PV_kW_addition = PV_kW_morning + PV_kW_midday + PV_kW_afternoon; % Put morning, midday, and afternoon matrix together
solarPowAvail = reshape(PV_kW_addition,[1,numDays*timesteps]);

%{
% Plots
timestep = 1:timesteps*3; % create time step array 
if strcmp(season,'winter')
    plot(timestep,solarPowAvail,'b','LineWidth',2)
    title('Winter Days')
    xlabel('timestep');ylabel('Power Output(kW)')
    set(gcf,'color','w'); grid on
elseif strcmp(season,'summer')
    plot(timestep,solarPowAvail,'y','LineWidth',2)
    title('Summer Days')
    xlabel('timestep');ylabel('Power Output(kW)')
    set(gcf,'color','w'); grid on
end
%}

end
