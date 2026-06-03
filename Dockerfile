FROM apache/superset:latest
USER root
RUN apt-get update && \
    apt-get install -y libldap2-dev libsasl2-dev ldap-utils && \
    pip install ldap3 python-ldap

COPY --chown=superset:root ./superset-excel/docker/pythonpath_dev/superset_config.py /app/docker/pythonpath_dev/superset_config.py
COPY --chown=superset:root ./superset-excel/superset/reports/models.py /app/superset/reports/models.py
COPY --chown=superset:root ./superset-excel/superset/commands/report/execute.py /app/superset/commands/report/execute.py
COPY --chown=superset:root ./superset-excel/superset/reports/notifications/email.py /app/superset/reports/notifications/email.py
COPY --chown=superset:root ./superset-excel/superset-frontend/src/features/reports/types.ts /app/superset-frontend/src/features/reports/types.ts
COPY --chown=superset:root ./superset-excel/superset-frontend/src/features/reports/ReportModal/index.tsx /app/superset-frontend/src/features/reports/ReportModal/index.tsx


USER superset
