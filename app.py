import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from utils import months_list, pre_process_data, filter_data, get_coi, get_inv_sold, get_inv_under_repair, \
    get_inv_picked, get_gatein_aging, get_dwell_time, format_kpi_value, news_card
from streamlit_option_menu import option_menu
from newsapi import NewsApiClient


st.set_page_config(page_title="Inventory Insights", page_icon="📊", layout="wide")

api = NewsApiClient(api_key='93e00f8b0c6f4d6696c7aaaaa0b009d0')
# ---------------------------------- Page Styling -------------------------------------

with open("css/style.css") as css:
    st.markdown(f'<style>{css.read()}</style>', unsafe_allow_html=True)

st.markdown("""
<style>
    [data-testid=stSidebar] {
        background-color: #708d81;
    }
    [data-testid=stMetricContainer] {
        background-color: #708d81;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------- Data Loading ------------------------------------

with st.sidebar:
    file_upload = st.file_uploader("Upload data file", type=["csv", "xlsx", "xls"])

df = pd.DataFrame()
if file_upload is not None:
    if file_upload.type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        df = pd.read_excel(file_upload, engine="openpyxl")
    elif file_upload.type == "application/vnd.ms-excel":  # Check if it's an XLS file
        df = pd.read_excel(file_upload)
    elif file_upload.type == "text/csv":  # Check if it's a CSV file
        df = pd.read_csv(file_upload, encoding=("UTF-8"))

    # ---------------------- Data Pre-processing --------------------------------------
    df = pre_process_data(df)
    year_list = list(set(df[df["Year"] != 0]["Year"].values))
    year_list.sort()

    # ---------------------------------------------------------------------------------
    menu = option_menu(menu_title=None, options=["Overview", "Sales & Costs",
                                                 "Inventory In vs. Out", "Sales Projection",
                                                 "News"], orientation="horizontal")

    # --------------------------------- Charts  ---------------------------------------
    if menu == "Overview":
        # ------------------------ Filters ------------------------------------------------
        location = st.sidebar.multiselect(label="Location",
                                          options=set(df["Location"].dropna().values),
                                          placeholder="All")
        depot = st.sidebar.multiselect(label="Depot",
                                       options=set(df["Depot"].dropna().values),
                                       placeholder="All")
        customer = st.sidebar.multiselect(label="Customer",
                                          options=set(df["Customer"].dropna().values),
                                          placeholder="All")
        unit = st.sidebar.multiselect(label="Unit#",
                                      options=set(df["Unit #"].dropna().values),
                                      placeholder="All")

        month = st.sidebar.multiselect(label="Month", options=months_list, default=["August", "October", "December"])
        year = st.sidebar.selectbox(label="Year", options=year_list, index=2)

        # -------------------- Filtered Data -------------------------------------------
        filtered_df = filter_data(df, location, depot, customer, unit)
        filtered_df = filtered_df[filtered_df["Year"] == year]
        filtered_data = filtered_df.copy()
        filtered_df_prev = filtered_df.copy()
        filtered_df = filtered_df[filtered_df["Month"].isin(month)]

        previous_month = months_list[months_list.index(month[0]) - 1]
        if previous_month == "December":
            filtered_df_prev = pd.DataFrame()
        else:
            filtered_df_prev = filtered_df_prev[filtered_df_prev["Month"] == previous_month]
        # ------------------------- Main Display ---------------------------------------
        if len(filtered_df) == 0:
            st.title("No Data Record found.")
        # -------------------------- KPIs calculation ----------------------------------

        cost_of_inventory, percentage_change_coi = get_coi(filtered_df, filtered_df_prev)
        inventory_sold, percentage_change_is = get_inv_sold(filtered_df, filtered_df_prev)
        inv_under_repair, percentage_change_ur = get_inv_under_repair(filtered_df, filtered_df_prev)
        inv_picked, percentage_change_ip = get_inv_picked(filtered_df, filtered_df_prev)
        gatein_aging, percentage_change_gia = get_gatein_aging(filtered_df, filtered_df_prev)
        dwell_time, percentage_change_dt = get_dwell_time(filtered_df, filtered_df_prev)

        # -------------------------- KPIs Display ---------------------------------------
        kpi_row = st.columns(6)
        kpi_row[0].metric(label="Cost of Inventory",
                          value=f"{format_kpi_value(cost_of_inventory)}",
                          delta=f"{percentage_change_coi:.1f}%")

        kpi_row[1].metric(label="Inventory Sold",
                          value=f"{format_kpi_value(inventory_sold)}",
                          delta=f"{percentage_change_is:.1f}%")

        kpi_row[2].metric(label="Inventory Undergoing Repairs",
                          value=f"{format_kpi_value(inv_under_repair)}",
                          delta=f"{percentage_change_ur:.1f}%")

        kpi_row[3].metric(label="Inventory Picked Up",
                          value=f"{inv_picked} items",
                          delta=f"{percentage_change_ip:.1f}%")

        kpi_row[4].metric(label="Gate In",  # Aging of Inventory (Gate In to Today)
                          value=f"{gatein_aging:.1f} days",
                          delta=f"{percentage_change_gia:.1f}%")
        try:
            kpi_row[5].metric(label="Gate Out",  # Dwell Time (Gate In to Sell Date)
                              value=f"{int(dwell_time)} days",
                              delta=f"{percentage_change_dt:.1f}%")
        except ValueError:
            kpi_row[5].metric(label="Gate Out",  # Dwell Time (Gate In to Sell Date)
                              value=f"{0} days",
                              delta=f"{percentage_change_dt:.1f}%")

        charts_row = st.columns(2)
        # -------------------------- Depot Activity ---------------------------------------

        depot_activity = filtered_df.groupby(['Depot', 'Size'])['Sale Price'].sum().unstack(fill_value=0)

        fig = go.Figure()
        for size in depot_activity.columns:
            fig.add_trace(go.Bar(x=depot_activity.index, y=depot_activity[size], name=size))

        fig.update_layout(barmode='group', xaxis_title='Depot', yaxis_title='Total Sales', title='DEPOT ACTIVITY',
                          xaxis={'categoryorder': 'total ascending'}, hovermode="x unified",
                          legend_title="Size", hoverlabel=dict(bgcolor="white",
                                                               font_color="black",
                                                               font_size=16,
                                                               font_family="Rockwell"
                                                               )
                          )
        charts_row[0].plotly_chart(fig, use_container_width=True)
        # -------------------------- Vendor Ratio ---------------------------------------
        vendor_counts = filtered_df['Vendor'].value_counts().reset_index()
        vendor_counts.columns = ['Vendor', 'Count']

        # Create a pie chart using Plotly
        fig = px.pie(vendor_counts, values='Count', names='Vendor', title='VENDOR DISTRIBUTION',
                     labels="percent+text", hole=0.3)
        fig.update_layout(hovermode="x unified",
                          legend_title="Vendors", hoverlabel=dict(bgcolor="white",
                                                                  font_color="black",
                                                                  font_size=16,
                                                                  font_family="Rockwell"
                                                                  )
                          )

        charts_row[1].plotly_chart(fig, use_container_width=True)
    # ------------------------------ Page 2 -----------------------------------------------
    if menu == "Sales & Costs":
        # ------------------------ Filters ------------------------------------------------
        location = st.sidebar.multiselect(label="Location",
                                          options=set(df["Location"].dropna().values),
                                          placeholder="All")
        depot = st.sidebar.multiselect(label="Depot",
                                       options=set(df["Depot"].dropna().values),
                                       placeholder="All")
        customer = st.sidebar.multiselect(label="Customer",
                                          options=set(df["Customer"].dropna().values),
                                          placeholder="All")
        unit = st.sidebar.multiselect(label="Unit#",
                                      options=set(df["Unit #"].dropna().values),
                                      placeholder="All")

        year = st.sidebar.selectbox(label="Year", options=year_list, index=2)

        # -------------------- Filtered Data -------------------------------------------
        filtered_data = filter_data(df, location, depot, customer, unit)
        filtered_data = filtered_data[filtered_data["Year"] == year]

        charts_row = st.columns(2)
        # -------------------------- Monthly Sales Scatter Plot ---------------------------
        fig = go.Figure()
        # Iterate over unique 'Size' values
        for size in filtered_data['Size'].unique():
            df_size = filtered_data[filtered_data['Size'] == size]
            df_size = pd.DataFrame(df_size.groupby("Month")["Sale Price"].sum())
            df_size = df_size.reindex(months_list, axis=0)
            df_size.reset_index(inplace=True)
            fig.add_trace(go.Scatter(
                x=df_size['Month'],
                y=df_size['Sale Price'],
                text=df_size['Sale Price'],
                mode='lines+markers+text',
                textposition='top center',
                name=size,
            ))
        fig.update_layout(title="Sales by Month", xaxis_title="Months", yaxis_title="Sales", hovermode="x unified",
                          legend_title="Size", hoverlabel=dict(bgcolor="white",
                                                               font_color="black",
                                                               font_size=16,
                                                               font_family="Rockwell"
                                                               )
                          )
        charts_row[0].plotly_chart(fig, use_container_width=True)
        # -------------------------- Sales vs. Cost Breakdown Bar plot --------------------
        grouped_data = filtered_data.groupby(['Month'])[['Storage Cost', 'Repair Cost', 'Purchase Cost']].sum()
        grouped_data = grouped_data.reindex(months_list, axis=0)

        # Create the stacked bar chart
        fig = go.Figure()
        for cost in grouped_data.columns:
            fig.add_trace(go.Bar(x=grouped_data.index, y=grouped_data[cost], name=cost))
        fig.update_layout(
            title="AVG. YEARLY SALES VS. COST BREAKDOWN",
            xaxis_title="Months", yaxis_title="Cost", barmode='stack', hovermode="x unified",
            legend_title="Cost", hoverlabel=dict(bgcolor="white",
                                                 font_color="black",
                                                 font_size=16,
                                                 font_family="Rockwell"
                                                 )
        )
        charts_row[1].plotly_chart(fig, use_container_width=True)

    # ------------------------------ Page 3 -----------------------------------------------
    if menu == "Inventory In vs. Out":
        # ------------------------ Filters ------------------------------------------------
        location = st.sidebar.multiselect(label="Location",
                                          options=set(df["Location"].dropna().values),
                                          placeholder="All")
        customer = st.sidebar.multiselect(label="Customer",
                                          options=set(df["Customer"].dropna().values),
                                          placeholder="All")
        unit = st.sidebar.multiselect(label="Unit#",
                                      options=set(df["Unit #"].dropna().values),
                                      placeholder="All")
        year = st.sidebar.selectbox(label="Year", options=year_list, index=2)

        # -------------------- Filtered Data -------------------------------------------
        filtered_data = filter_data(df, location, depot=None, customer=customer, unit=unit)
        filtered_df = filtered_data[filtered_data["Year"] == year]

        charts_row = st.columns(2)
        inv_in_out_data = filtered_df.groupby(["Month"])["Gate In", "Gate Out"].count().reset_index()
        inv_in_out_data["Gate Out"] = (-1) * inv_in_out_data["Gate Out"]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(x=inv_in_out_data["Month"], y=inv_in_out_data["Gate In"], name="Gate In Items")
        )
        fig.add_trace(
            go.Bar(x=inv_in_out_data["Month"], y=inv_in_out_data["Gate Out"], name="Gate Out Items",
                   marker=dict(color="red"))
        )
        fig.update_layout(
            barmode='group',  # This combines positive and negative bars for each month
            title='Gate In vs. Gate Out over-time',
            xaxis_title='Month',
            yaxis_title='Items Count',
            hovermode="x unified",
            hoverlabel=dict(bgcolor="white",
                            font_color="black",
                            font_size=12,
                            font_family="Rockwell"
                            ))

        charts_row[0].plotly_chart(fig, use_container_width=True)
        # ------------------------------------------------------------------------------------
        inv_in_out_data = filtered_df.groupby(["Depot"])["Gate In", "Gate Out"].count().reset_index()
        inv_in_out_data["Gate Out"] = (-1) * inv_in_out_data["Gate Out"]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(x=inv_in_out_data["Depot"], y=inv_in_out_data["Gate In"], name="Gate In Items")
        )
        fig.add_trace(
            go.Bar(x=inv_in_out_data["Depot"], y=inv_in_out_data["Gate Out"], name="Gate Out Items",
                   marker=dict(color="red"))
        )
        fig.update_layout(
            barmode='group',  # This combines positive and negative bars for each month
            title='Gate In vs. Gate Out w.r.t Depot',
            xaxis_title='Depot',
            yaxis_title='Items Count',
            hovermode="x unified",
            hoverlabel=dict(bgcolor="white",
                            font_color="black",
                            font_size=12,
                            font_family="Rockwell"
                            ))

        charts_row[1].plotly_chart(fig, use_container_width=True)
    # ------------------------------ Page 4 -----------------------------------------------
    if menu == "News":
        year = st.sidebar.selectbox(label="Year", options=year_list, index=2)
        filtered_df = df[df["Year"] == year]
        supplier = st.sidebar.selectbox(label="Vendor", options=set(filtered_df["Vendor"].dropna().values))

        response_data = api.get_everything(q=F"{supplier} suppliers",
                                           sort_by="publishedAt",
                                           language="en",
                                           # domains="marketscreener.com"
                                           )
        # Check if there are articles to display
        if response_data['totalResults'] > 0:
            news_col = st.columns((3, 1))
            for article in response_data['articles']:
                st.markdown(news_card.format(title=article['title'], image=article['urlToImage'],
                                             description=article['content'],
                                             published_at=f"{article['source']['name']} - {article['publishedAt']}",
                                             url=article["url"]),
                            unsafe_allow_html=True)
                st.write("---")
        else:
            st.info("No news found")

    # ------------------------------ Page 5 -----------------------------------------------
    if menu == "Sales Projection":
        st.write("to be implemented...")
        st.dataframe(df, use_container_width=True)

# -------------------------------------------------------------------------------------------------------
