FROM apache/superset:latest
USER root
RUN apt-get update && \
    apt-get install -y libldap2-dev libsasl2-dev ldap-utils
RUN pip install --upgrade pip
RUN pip install ldap3

COPY --chown=superset:root ./superset-excel/docker/pythonpath_dev/superset_config.py /app/docker/pythonpath_dev/superset_config.py
COPY --chown=superset:root ./superset-excel/superset/reports/. /app/superset/reports/.
COPY --chown=superset:root ./superset-excel/superset/commands/. /app/superset/commands/.
COPY --chown=superset:root ./superset-excel/superset-frontend/src/features/reports/types.ts /app/superset-frontend/src/features/reports/types.ts
COPY --chown=superset:root ./superset-excel/superset-frontend/src/features/reports/ReportModal/index.tsx /app/superset-frontend/src/features/reports/ReportModal/index.tsx


#USER superset
