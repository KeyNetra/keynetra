# Polar-like flat rules supported by KeyNetra loader
allow action=deploy priority=20 policy_id=ops-deploy-allow role=ops environment=staging
allow action=restart_service priority=30 policy_id=ops-restart-allow role=sre

deny action=deploy priority=90 policy_id=ops-deploy-deny-prod role=contractor environment=production
