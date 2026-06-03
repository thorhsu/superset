# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
# This file is included in the final Docker image and SHOULD be overridden when
# deploying the image to prod. Settings configured here are intended for use in local
# development environments. Also note that superset_config_docker.py is imported
# as a final step as a means to override "defaults" configured here
#
import logging
import os
import sys
from datetime import timedelta

import pandas as pd

from celery.schedules import crontab
from flask_caching.backends.filesystemcache import FileSystemCache
from superset.security import SupersetSecurityManager
from flask_appbuilder.security.manager import AUTH_LDAP, AUTH_DB
from sqlalchemy import create_engine, text
from ldap3 import Server, Connection, SAFE_SYNC


logger = logging.getLogger()

DATABASE_DIALECT = os.getenv("DATABASE_DIALECT")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_HOST = os.getenv("DATABASE_HOST")
DATABASE_PORT = os.getenv("DATABASE_PORT")
DATABASE_DB = os.getenv("DATABASE_DB")

EXAMPLES_USER = os.getenv("EXAMPLES_USER")
EXAMPLES_PASSWORD = os.getenv("EXAMPLES_PASSWORD")
EXAMPLES_HOST = os.getenv("EXAMPLES_HOST")
EXAMPLES_PORT = os.getenv("EXAMPLES_PORT")
EXAMPLES_DB = os.getenv("EXAMPLES_DB")

# The SQLAlchemy connection string.
SQLALCHEMY_DATABASE_URI = (
    f"{DATABASE_DIALECT}://"
    f"{DATABASE_USER}:{DATABASE_PASSWORD}@"
    f"{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_DB}"
)
logger.info(f"database uri: {SQLALCHEMY_DATABASE_URI}")

SQLALCHEMY_EXAMPLES_URI = (
    f"{DATABASE_DIALECT}://"
    f"{EXAMPLES_USER}:{EXAMPLES_PASSWORD}@"
    f"{EXAMPLES_HOST}:{EXAMPLES_PORT}/{EXAMPLES_DB}"
)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_CELERY_DB = os.getenv("REDIS_CELERY_DB", "0")
REDIS_RESULTS_DB = os.getenv("REDIS_RESULTS_DB", "1")

RESULTS_BACKEND = FileSystemCache("/app/superset_home/sqllab")

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": REDIS_RESULTS_DB,
}
DATA_CACHE_CONFIG = CACHE_CONFIG
THUMBNAIL_CACHE_CONFIG = CACHE_CONFIG

SCREENSHOT_LOCATE_WAIT = 100
SCREENSHOT_LOAD_WAIT = 600

# WebDriver configuration
# If you use Firefox or Playwright with Chrome, you can stick with default values
# If you use Chrome and are *not* using Playwright, then add the following WEBDRIVER_TYPE and WEBDRIVER_OPTION_ARGS
# Change driver type to remote
WEBDRIVER_TYPE = "remote"
# The URL for the remote selenium container
# 'http://standalone-chrome' is the service name from your docker-compose
WEBDRIVER_REMOTE_COMMAND_EXECUTOR = "http://standalone-chrome:4444/wd/hub"
WEBDRIVER_OPTION_ARGS = [
    "--headless",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--window-size=1920,1080"
]

# This is for internal use, you can keep http
WEBDRIVER_BASEURL = "http://superset_app:8088" # When running using docker compose use "http://superset_app:8088'
# This is the link sent to the recipient. Change to your domain, e.g. https://superset.mydomain.com
WEBDRIVER_BASEURL_USER_FRIENDLY = "http://192.168.32.132:8088"

class CeleryConfig:
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_CELERY_DB}"
    imports = (
        "superset.sql_lab",
        "superset.tasks.scheduler",
        "superset.tasks.thumbnails",
        "superset.tasks.cache",
    )
    result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_RESULTS_DB}"
    worker_prefetch_multiplier = 3
    task_acks_late = True
    task_annotations = {
        "sql_lab.get_sql_results": {
            "rate_limit": "100/s",
        },
    }
    beat_schedule = {
        "reports.scheduler": {
            "task": "reports.scheduler",
            "schedule": crontab(minute="*", hour="*"),
        },
        "reports.prune_log": {
            "task": "reports.prune_log",
            "schedule": crontab(minute=10, hour=0),
        },
    }


CELERY_CONFIG = CeleryConfig

ALERT_REPORTS_NOTIFICATION_DRY_RUN = False
SQLLAB_CTAS_NO_LIMIT = True

# --- Placeholder settings to satisfy Superset's startup check ---
AUTH_TYPE = AUTH_LDAP
AUTH_LDAP_SERVER = "ldap://1992sharetea.com"  # Even if manual, this must exist
AUTH_LDAP_SEARCH = "DC=1992sharetea,DC=com"   # Must exist for validation
# ----------------------------------------------------------------
pg_engine = create_engine(SQLALCHEMY_DATABASE_URI)
class CustomDualSecurityManager(SupersetSecurityManager):  # Inherit from SupersetSecurityManager
    def auth_user_ldap(self, username, password):
        # 1. Try Local Database (Old accounts with passwords)
        user = self.auth_user_db(username, password)
        if user:
            logger.info(f"Local DB Login successful for {username}")
            return user

        # 2. FALLBACK:  AD Configuration from your settings
        AD_HOST = "1992sharetea.com"
        AD_DOMAIN = "1992sharetea"
        AD_BASE_DN = f'DC={AD_DOMAIN},DC=com'
        
        # Consistent with your original logic
        username_with_domain = f"{username}@{AD_HOST}"
        logger.info('username:' + username_with_domain)

        server = Server(AD_HOST, get_info='ALL')
        
        try:
            with (Connection(server, user=username_with_domain, password=password, client_strategy=SAFE_SYNC) as conn):
                if not conn.bind():
                    logger.error(f"AD Bind failed for {username}")
                    return None
                
                # Search for user details (email)
                conn.search(AD_BASE_DN, f'(sAMAccountName={username})', attributes=['*'])
                ad_entries = conn.search(AD_BASE_DN, f'(sAMAccountName={username})', attributes=['*'])
                if not ad_entries[0]:
                    return None
                
                email = str(ad_entries[2][0]['attributes']['mail'])
                logger.info(f"{email} Authentication successful!")                
                logger.info('email:' + email + ', login success')

                # 2. Sync to Superset DB
                # auth_user_remote_user will create the user if they don't exist
                # 1. Manually check if user exists or create them
                ab_user = self.find_user(username=username)
                
                df = pd.read_sql("""select u.user_id, u.user_name, u.email email, u.unit_name, ou.subunit_names, ou.oid, u.anchor_unit_oids
                    from users u inner join organization_units ou on ou.oid = u.unit_oid
                    inner join organizations o on o.oid = ou.organization_oid
                    where u.email = %(email)s and u.organization_id = 'LF000000'""", pg_engine, params={'email': email})

                # 找出user應該所屬的部門
                first_name = username
                last_name = "AD_User"
                unit_oids = []
                for index, row in df.iterrows():
                    row_dict = row.to_dict()
                    first_name = row_dict['user_name'] if row_dict['user_name'] else first_name
                    last_name = row_dict['user_id'] if row_dict['user_id'] else last_name
                    if row_dict['anchor_unit_oids']:
                        for oid in row_dict['anchor_unit_oids'].split(','):
                            if oid not in unit_oids:
                                unit_oids.append(oid)

                ids = "'" + "','".join(unit_oids) + "'"



                logger.info("unit_oids:" + ",".join(unit_oids))
                df_organizations = pd.read_sql("select oid, unit_name, subunit_oids from organization_units where oid in ("+ ids +")", pg_engine)
                for index, row in df_organizations.iterrows():
                    row_dict = row.to_dict()
                    if row_dict['subunit_oids']:
                        subunit_oids = row_dict['subunit_oids'].split(',')
                        for subunit_oid in subunit_oids:
                            if subunit_oid not in unit_oids:
                                unit_oids.append(subunit_oid)

                df_groups = pd.read_sql("select * from ab_group order by id desc", pg_engine)
                logger.info("df groups:" + str(len(df_groups.index)) + " rows")
                if ab_user:
                    ab_user.first_name = first_name
                    ab_user.last_name = last_name
                    logger.info('ab_user exist ' + str(ab_user.id))
                else:
                    # If user doesn't exist, create them with the email from AD
                    ab_user = self.add_user(
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        role=self.find_role(self.auth_user_registration_role)
                    )                
                user_id = ab_user.id
                logger.info("user id:" + str(user_id))
                df_table = []

                pg_engine.execute(text("""delete from ab_user_group ug
                    using ab_group g  
                    where g.id = ug.group_id 
                        and g.oid is not null
                        and ug.user_id = """ + str(user_id) ))

                max_id = 1
                logger.info("max id" + str(max_id))
                for index, row in df_groups.iterrows():
                    row_dict = row.to_dict()
                    if row_dict['id'] > max_id:
                        max_id = int(row_dict['id'])
                    logger.info("max id" + str(max_id))
                    if row_dict['oid'] in unit_oids:
                        max_id += 1
                        df_table.append({
                            'id': max_id,
                            'user_id': user_id,
                            'group_id': row_dict['id'],
                        })
                my_df = pd.DataFrame(df_table)
                my_df.to_sql("ab_user_group", pg_engine, if_exists="append", index=False)
                logger.info("df table:" + str(len(df_table)) + " rows")
                # 2. Now return the authenticated user object
                return ab_user

        except Exception as e:
            logger.error(f"Custom AD Authentication Error: {str(e)}")
            return None

# Apply the Custom Manager
CUSTOM_SECURITY_MANAGER = CustomDualSecurityManager
AUTH_USER_REGISTRATION = True
# To truly hide the "Register" link in many versions, set:
AUTH_USER_SELF_REGISTRATION = False

# Re-verify this role exists in your DB. Standard roles: "Admin", "Alpha", "Gamma", "Public"
AUTH_USER_REGISTRATION_ROLE = "Gamma" 

# Fix for the ReCaptcha bug
RECAPTCHA_PUBLIC_KEY = "dummy"
RECAPTCHA_PRIVATE_KEY = "dummy"

# Set a short absolute session timeout
# The default is 31 days, which is NOT recommended for production.
PERMANENT_SESSION_LIFETIME = timedelta(hours=3)

# session security
# Enforce secure cookie flags to prevent browser-based attacks
SESSION_COOKIE_SECURE = True      # Transmit cookie only over HTTPS
SESSION_COOKIE_HTTPONLY = True    # Prevent client-side JS from accessing the cookie
SESSION_COOKIE_SAMESITE = 'Lax'   # Provide protection against CSRF attacks


def COMMON_BOOTSTRAP_OVERRIDES_FUNC(bootstrap_data: dict) -> dict:
    """
    Force the frontend to think registration is disabled to hide the UI button,
    even if the backend needs it enabled for OAuth/SAML provisioning.
    """
    conf = bootstrap_data.get("conf", {})
    return {
        **bootstrap_data,
        "conf": {
            **conf,
            "AUTH_USER_REGISTRATION": False,
        },
    }


log_level_text = os.getenv("SUPERSET_LOG_LEVEL", "INFO")
LOG_LEVEL = getattr(logging, log_level_text.upper(), logging.INFO)

# Email configuration
SMTP_HOST = "203.69.82.12"      
SMTP_STARTTLS = False                    # Use True for port 587
SMTP_SSL = False                        # Use True for port 465
SMTP_PORT = 25                         # Standard ports: 25, 465, 587
SMTP_USER = "system.auto@1992sharetea.com.tw"
SMTP_PASSWORD = ""
SMTP_MAIL_FROM = "system.auto@1992sharetea.com.tw"
EMAIL_REPORTS_SUBJECT_PREFIX = "[Superset] " # optional - overwrites default value in config.py of "[Report] "


FEATURE_FLAGS = {
    "ALERT_REPORTS": True,
    "REPORT_SCHEDULES": True,
    "ALERTS_ATTACH_REPORTS": True,
    "ALLOW_ADHOC_SUBQUERY": True, # Sometimes required for complex table queries
    "EXCEL_EXPORT": True,         # Force enable Excel as a format
    "ENABLE_TEMPLATE_PROCESSING": True, # enable Jinja template
    "DASHBOARD_RBAC": True, # enable fine grained dashboard access control by roles
}

# Ensure the worker is allowed to process data for these types
# This is a hidden config in some 6.0 builds
OUTPUT_EXCEL_FORMAT = "xlsx"


if os.getenv("CYPRESS_CONFIG") == "true":
    # When running the service as a cypress backend, we need to import the config
    # located @ tests/integration_tests/superset_test_config.py
    base_dir = os.path.dirname(__file__)
    module_folder = os.path.abspath(
        os.path.join(base_dir, "../../tests/integration_tests/")
    )
    sys.path.insert(0, module_folder)
    from superset_test_config import *  # noqa

    sys.path.pop(0)

#
# Optionally import superset_config_docker.py (which will have been included on
# the PYTHONPATH) in order to allow for local settings to be overridden
#
try:
    import superset_config_docker
    from superset_config_docker import *  # noqa: F403

    logger.info(
        f"Loaded your Docker configuration at [{superset_config_docker.__file__}]"
    )
except ImportError:
    logger.info("Using default Docker config...")
