# Power BI import package initialization
#
# Core generation modules:
#   pbip_generator, tmdl_generator, visual_generator,
#   m_query_generator, import_to_powerbi, validator, migration_report
#
# Advanced modules (ported from TableauToPowerBI):
#   dax_optimizer, dax_recipes, dax_query_generator, model_templates,
#   governance, security_validator, monitoring, alerts_generator,
#   recovery_report, sla_tracker, schema_drift, equivalence_tester,
#   regression_suite, visual_diff, marketplace, api_server,
#   notebook_api, paginated_generator, permission_mapper, llm_client,
#   geo_passthrough, refresh_generator
#
# Fabric-native generation:
#   fabric_constants, fabric_naming, lakehouse_generator,
#   dataflow_generator, notebook_generator, pipeline_generator,
#   fabric_semantic_model_generator, fabric_project_generator,
#   calc_column_utils
#
# Multi-app merge engine:
#   shared_model, thin_report_generator, merge_assessment,
#   merge_config, merge_report_html, global_assessment
#
# Portfolio assessment:
#   server_assessment
#
# Deployment subpackage (powerbi_import.deploy):
#   auth, client, deployer, utils, config/
#   bundle_deployer, multi_tenant, pbi_client, pbi_deployer
__version__ = '10.1.0'
