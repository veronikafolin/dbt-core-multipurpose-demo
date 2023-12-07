from datetime import timedelta
from airflow import DAG
from airflow.models import TaskInstance
from airflow.models.baseoperator import chain
from airflow.operators.python import BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils import dates
from airflow.utils.state import State
from airflow.utils.trigger_rule import TriggerRule
from airflow_dbt.operators.dbt_operator import (
    DbtSnapshotOperator,
    DbtRunOperator,
    DbtTestOperator,
)

default_args = {
    'start_date': dates.days_ago(0),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(dag_id='build_dim_customer', default_args=default_args, schedule_interval=None):

    dbt_snapshot_customer = DbtSnapshotOperator(
        task_id='dbt_snapshot_customer',
        models='customer_snapshot'
    )

    check_customer_freshness = DbtTestOperator(
        task_id='check_customer_freshness',
        select='stg_customer,tag:freshness'
    )


    def branch_func_on_customer_freshness(**kwargs):
        execution_date = kwargs['execution_date']
        task_status = TaskInstance(check_customer_freshness, execution_date).current_state()
        if task_status == State.SUCCESS:
            return 'trigger_nation_dag'
        else:
            return 'dbt_run_stg_customer'

    branch_on_customer_freshness = BranchPythonOperator(
        task_id='branch_on_customer_freshness',
        python_callable=branch_func_on_customer_freshness,
        provide_context=True
    )

    dbt_run_stg_customer = DbtRunOperator(
        task_id='dbt_run_stg_customer',
        models='stg_customer'
    )

    dbt_test_stg_customer = DbtTestOperator(
        task_id='dbt_test_stg_customer',
        models='stg_customer'
    )

    trigger_nation_dag = TriggerDagRunOperator(
        task_id="trigger_nation_dag",
        trigger_dag_id="build_int_nation",
        trigger_rule=TriggerRule.ALL_DONE,
        wait_for_completion=True
    )

    dbt_run_dim_customer = DbtRunOperator(
        task_id='dbt_run_dim_customer',
        models='dim_customer'
    )

    dbt_test_dim_customer = DbtTestOperator(
        task_id='dbt_test_dim_customer',
        models='dim_customer'
    )

    dbt_snapshot_customer >> check_customer_freshness >> branch_on_customer_freshness >> [trigger_nation_dag, dbt_run_stg_customer]
    dbt_run_stg_customer >> dbt_test_stg_customer >> trigger_nation_dag
    trigger_nation_dag >> dbt_run_dim_customer >> dbt_test_dim_customer


with DAG(dag_id='build_int_nation', default_args=default_args, schedule_interval=None):

    dbt_run_stg_nation = DbtRunOperator(
        task_id='dbt_run_stg_nation',
        models='stg_nation'
    )

    dbt_test_stg_nation = DbtTestOperator(
        task_id='dbt_test_stg_nation',
        models='stg_nation'
    )

    dbt_run_stg_region = DbtRunOperator(
        task_id='dbt_run_stg_region',
        models='stg_region'
    )

    dbt_test_stg_region = DbtTestOperator(
        task_id='dbt_test_stg_region',
        models='stg_region'
    )

    dbt_run_int_nation = DbtRunOperator(
        task_id='dbt_run_int_nation',
        models='int_nation'
    )

    dbt_test_int_nation = DbtTestOperator(
        task_id='dbt_test_int_nation',
        models='int_nation'
    )

    chain((dbt_run_stg_nation, dbt_run_stg_region), (dbt_test_stg_nation, dbt_test_stg_region), dbt_run_int_nation,
          dbt_test_int_nation)
