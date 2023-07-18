import streamlit as st

mac_to_name = {
            '70b3d52c3126': '7501',
            '70b3d52c3127': '7501',
            '70b3d52c3b92': '7502',
            '70b3d52c3b93': '7502',
            '70b3d52c3142': '7503',
            '70b3d52c3143': '7503',
            '70b3d52c314c': '7504',
            '70b3d52c314d': '7504',
            '70b3d52c3a92': '7505',
            '70b3d52c3a93': '7505',
            '70b3d52c3716': '9501',
            '70b3d52c3717': '9501',
            # missing 9502
            '70b3d52c3728': '9503',
            '70b3d52c3729': '9503',
            '70b3d52c3746': '9504',
            '70b3d52c3747': '9504',
            '70b3d52c374A': '9505',
            '70b3d52c374B': '9505',
            
}


ebuses = [f'750{i}' for i in range(1, 6)] + [f'950{i}' for i in range(1, 6)]


# dataframe string formatting
dash_column_config = {
    "soc": st.column_config.ProgressColumn(
        "State of Charge",
        help="Battery Percentage of Bus",
        format="%d%%",
        width='medium',
        min_value=0,
        max_value=100,
    ),
    "vehicle": st.column_config.TextColumn(
        "Coach",
        help="Bus Identification Number",
        # format="%d",
    ),
    "odometer": st.column_config.NumberColumn(
        "Odometer (mi)",
        help="Bus Odometer Reading in miles",
    ),
    "last_transmission": st.column_config.DatetimeColumn(
        "Last Transmission Time",
        help="Time of Last Transmission",
        format="hh:mmA MM/DD/YYYY",
    ),
    "status": st.column_config.CheckboxColumn("Status")
}