import os,base64
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, date, timedelta
import urllib.request as urllib2
import tempfile
import pandas as pd
import pyarrow as pa
from deltalake import DeltaTable
from deltalake.writer import write_deltalake
import duckdb 
import re ,shutil
from urllib.request import urlopen

st.set_page_config(
    page_title="Example of Delta Table and DuckDB",
    page_icon="✅",
    layout="wide",
)

st_autorefresh(interval=5 * 60 * 1000, key="dataframerefresh")

# dashboard title
st.title("Example of Delta Table and DuckDB")

col1, col2 = st.columns([1, 1])


def get_file_path(filename):
    return os.path.join(tempfile.gettempdir(), filename)

def getfiles(Path,url):    
    
    
    result = urlopen(url).read().decode('utf-8')
    pattern = re.compile(r'[\w.]*.zip')
    filelist1 = pattern.findall(result)
    filelist_unique = dict.fromkeys(filelist1)
    filelist_sorted=sorted(filelist_unique, reverse=True)
    filelist = filelist_sorted[:288]
    
    table_path = Path 
    try:
        df = DeltaTable(table_path).to_pandas()
    except:
        df=pd.DataFrame(columns=['file']) 
    
    df= df['file'].unique()
    #print (df)

    current = df.tolist()
    #print(current)

    files_to_upload = list(set(filelist) - set(current))
    files_to_upload = list(dict.fromkeys(files_to_upload)) 
    return files_to_upload


def load(files_to_upload,table_path,url): 
    if len(files_to_upload) != 0 :
      for x in files_to_upload:
            with urlopen(url+x) as source, open(get_file_path(x), 'w+b') as target:
                shutil.copyfileobj(source, target)
            df = pd.read_csv(get_file_path(x),skiprows=1,usecols=["SETTLEMENTDATE", "DUID", "SCADAVALUE"],parse_dates=["SETTLEMENTDATE"])
            df=df.dropna(how='all') #drop na
            df['SETTLEMENTDATE']= pd.to_datetime(df['SETTLEMENTDATE'])
            df['Date'] = df['SETTLEMENTDATE'].dt.date
            df['file'] = x
            tb=pa.Table.from_pandas(df,preserve_index=False)
            my_schema = pa.schema([
                      pa.field('SETTLEMENTDATE', pa.timestamp('us')),
                      pa.field('DUID', pa.string()),
                      pa.field('SCADAVALUE', pa.float64()),
                      pa.field('Date', pa.date32()),
                      pa.field('file', pa.string())
                      ]
                                                       )
            xx=tb.cast(target_schema=my_schema)
            #print(xx)
            write_deltalake(table_path, xx,mode='append',partition_by=['Date'])
            

# Get table as pyarrow table
def read(files_to_upload,table_path): 
     dt = DeltaTable(table_path).to_pyarrow_table()
     return dt
            

# Define the Path to your Delta Table.
url = "http://nemweb.com.au/Reports/Current/Dispatch_SCADA/"
table_path = "xxx/"
 
files_to_upload=getfiles(table_path,url)
load(files_to_upload,table_path,url)
dt = read(files_to_upload,table_path)


# Query arrow table as an ordinary SQL Table.
con = duckdb.connect()
results =con.execute('''
with xx as (Select SETTLEMENTDATE, (SETTLEMENTDATE - INTERVAL 10 HOUR) as LOCALDATE , DUID,MIN(SCADAVALUE) as mwh from  dt group by all)
Select SETTLEMENTDATE,LOCALDATE, sum(mwh) as mwh from  xx group by all order by SETTLEMENTDATE desc
''').arrow()
results = results.to_pandas()
column = results["SETTLEMENTDATE"]
now = str (column.max())
st.subheader("Latest Updated: " + now)

#localdate is just a stuid hack, Javascript read datetime as UTC not local time :(
import altair as alt
c = alt.Chart(results).mark_area().encode( x='LOCALDATE:T', y='mwh:Q',
                                          tooltip=['LOCALDATE','mwh']).properties(
                                            width=1200,
                                            height=600)
st.write(c)



col1.button("Refresh")
#Download Button
df=results[['SETTLEMENTDATE','mwh']]

def convert_df(df):
     # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return df.to_csv().encode('utf-8')

csv = convert_df(df)
col2.download_button(
     label="Download data as CSV",
     data=csv,
     file_name='large_df.csv',
     mime='text/csv',
 )
#######################################33
link='[Blog](https://datamonkeysite.com/2022/06/28/using-delta-lake-with-python/)'
col2.markdown(link,unsafe_allow_html=True)

link='[Data Source](http://nemweb.com.au/Reports/Current/Dispatch_SCADA/)'
col1.markdown(link,unsafe_allow_html=True)

st.write(files_to_upload)

