# import networkx as nx
# import pandas as pd
# import dask.dataframe as dd
# import numpy as np
# import ast
# import dask
# from dask.distributed import Client
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from ingest_data import ingest_data
from preprocessing import initial_preprocessing
from add_edges_to_graph import add_edges_to_graph
from data_split import data_split
from feature_extraction import extract_graph_features
from dask_handling import create_dask_dataframe
from graph_operations import merge_trans_with_gf
from upload_files_to_bucket import upload_file_to_gcs
from readValidationData import download_data_from_bucket
from preprocessingTest import initial_preprocessing_test
from perform_eda import perform_eda
from perform_visualization_EDA import analyze_with_tfdv
from airflowdag import data_split_task
from model_inference import model_inference_def

# G = None 
# scheduler_address = 'tcp://10.128.0.5:8786'

# # Connect to the Dask cluster
# client = Client(scheduler_address)
# client.upload_file('ingest_data.py')
# client.upload_file('preprocessing.py')
# client.upload_file('pre_extraction.py')
# client.upload_file('create_graph.py')
# client.upload_file('graph_operations.py')
# client.upload_file('dask_handling.py')
# client.upload_file('add_edges_to_graph.py')
# client.upload_file('data_split.py')
# client.upload_file('feature_Extraction.py')
# client.upload_file('graph_operations.py')

default_args = {
    'owner': 'amlmlops',
    'depends_on_past': False,
    'start_date': datetime(2024, 3, 11),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(hours=5),
} 


with DAG(
    dag_id='DAG2',
    default_args=default_args,
    description="Antimoney Laundering Project",
    start_date=datetime(2024, 3, 10, 2),
    schedule_interval="@daily",
    max_active_runs=1
) as dag:    

   # Tasks will be defined here
    read_validation_data_task = PythonOperator(
        task_id='read_validation_data',
        python_callable=download_data_from_bucket,
        dag=dag
    )

    perform_EDA_task = PythonOperator(
        task_id='perform_EDA',
        python_callable=perform_eda,
        #op_kwargs={'df': read_validation_data_task.output['test_df']},
        dag=dag
    )
    
    perform_visualization_task = PythonOperator(
        task_id='perform_visualization_EDA',
        python_callable=analyze_with_tfdv,
        #op_kwargs={'df1': data_split_task.output[2], 'df2': data_split_task.output[3] },
        dag=dag
    )
    
    preprocess_validation_data_task = PythonOperator(
        task_id='initial_preprocessing_test',
        python_callable=initial_preprocessing_test,
        #op_kwargs={'raw_data': read_validation_data_task.output['test_df'],'first_timestamp': read_validation_data_task.output['first_timestamp'], 'currency_dict': read_validation_data_task.output['currency_dict'] ,'payment_format_dict': read_validation_data_task.output['payment_format_dict'],'bank_account_dict': read_validation_data_task.output['bank_account_dict']},
        dag=dag
    )    

    add_edges_task = PythonOperator(
        task_id='add_edges_to_graph',
        python_callable=add_edges_to_graph,
        op_kwargs={'dagtype': 'inference'},
        #op_kwargs={'initial_preprocessed_ddf': preprocess_validation_data_task.output['ddf']},  # Pass the output of extract_features_task to create_graph
        dag=dag
    )

    feature_Extraction_task = PythonOperator(
        task_id='extract_graph_features',
        python_callable=extract_graph_features,
        #op_kwargs={'G': add_edges_task.output['G'], 'train_graph_ddf': add_edges_task.output['ddf']},  # Pass the outputs of preprocess_data_task and create_graph_task
        dag=dag
    )

    #create_dask_dataframe_task = PythonOperator(
    #    task_id='create_dask_dataframe',
    #    python_callable=create_dask_dataframe,
    #    op_kwargs={'graph_features': feature_Extraction_task.output},  # Pass the output of process_graph_data_task to create_dask_dataframe
    #    dag=dag
    #)

    merge_trans_with_gf_task = PythonOperator(
        task_id='merge_trans_with_gf',
        python_callable=merge_trans_with_gf,
        #op_kwargs={'transactions_ddf': add_edges_task.output['ddf'], 'graph_features_ddf': create_dask_dataframe_task.output},  # Pass the outputs of preprocess_data_task and create_dask_dataframe_task
        dag=dag
    )

    upload_files_to_gcs_task = PythonOperator(
        task_id='upload_files_to_gcs',
        op_kwargs={'dagtype': 'inference'},
        python_callable=upload_file_to_gcs,
        provide_context=True,  # Allows accessing task context
        #op_kwargs={'bucket_name': 'aml_mlops_bucket' ,'file_paths': [add_edges_task.output['G'], preprocess_validation_data_task.output['first_timestamp'], preprocess_validation_data_task.output['currency_dict'], preprocess_validation_data_task.output['payment_format_dict'], 
        #                          preprocess_validation_data_task.output['bank_account_dict'], preprocess_validation_data_task.output['account_dict'], merge_trans_with_gf_task.output]},  # Define file paths here
        dag=dag
    )

    prediction_task = PythonOperator(
        task_id='model_inference',
        python_callable=model_inference_def,
        provide_context=True,  # Allows accessing task context
        dag=dag
    )

    
    #read_validation_data_task >> perform_EDA_task >> preprocess_validation_data_task >> add_edges_task >> feature_Extraction_task >> merge_trans_with_gf_task >> upload_files_to_gcs_task 

     # Set up dependencies
    perform_EDA_task.set_upstream(read_validation_data_task)
    perform_visualization_task.set_upstream(read_validation_data_task)
    preprocess_validation_data_task.set_upstream(read_validation_data_task)
    add_edges_task.set_upstream(preprocess_validation_data_task)
    feature_Extraction_task.set_upstream(add_edges_task)
    merge_trans_with_gf_task.set_upstream([add_edges_task, feature_Extraction_task])
    upload_files_to_gcs_task.set_upstream([add_edges_task, preprocess_validation_data_task, merge_trans_with_gf_task])
    prediction_task.set_upstream(merge_trans_with_gf_task)