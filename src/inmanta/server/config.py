"""
    Copyright 2016 Inmanta

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

    Contact: code@inmanta.com
"""

from inmanta.config import Option, is_int, is_bool, is_time, is_list, is_str_opt
from inmanta.config import state_dir, log_dir
import logging


LOGGER = logging.getLogger(__name__)

# flake8: noqa: H904

#############################
# Database
#############################

db_host = \
    Option("database", "host", "localhost",
           "Hostname or IP of the mongo server")
db_port = \
    Option("database", "port", 27017,
           "The port of the mongo server", is_int)
db_name = \
    Option("database", "name", "inmanta",
           "The name of the database on the mongo server")

#############################
# server_rest_transport
#############################

transport_port = \
    Option("server_rest_transport", "port", 8888,
           "The port on which the server listens for connections")


#############################
# server
#############################

server_username = \
    Option("server", "username", None,
           "Username required to connect to this server. Leave blank to disable auth", is_str_opt)

server_password = \
    Option("server", "password", None,
           "Password required to connect to this server. Leave blank to disable auth", is_str_opt)

server_ssl_key = \
    Option("server", "ssl_key_file", None,
           "Server private key to use for this server Leave blank to disable SSl", is_str_opt)

server_ssl_cert = \
    Option("server", "ssl_cert_file", None,
           "SSL certificate file for the server key. Leave blank to disable SSL", is_str_opt)


server_fact_expire = \
    Option("server", "fact-expire", 3600,
           "After how many seconds will discovered facts/parameters expire", is_time)

# server_ssl_key  = \
#     Option("server", "fact-expire", 3600,
#            "After how many seconds will discovered facts/parameters expire", is_time)
#
# ssl_cert_file


def default_fact_renew():
    """ server.fact-expire/3 """
    return str(int(server_fact_expire.get() / 3))


def validate_fact_renew(value):
    """ time; < server.fact-expire """
    out = int(value)
    if not out < server_fact_expire.get():
        LOGGER.warn("can not set fact_renew to %d, must be smaller than fact-expire (%d), using %d instead" %
                    (out, server_fact_expire.get(), default_fact_renew()))
        out = default_fact_renew()
    return out

server_fact_renew = \
    Option("server", "fact-renew", default_fact_renew,
           """After how many seconds will discovered facts/parameters be renewed?
This value needs to be lower than fact-expire""", validate_fact_renew)

server_fact_resource_block = \
    Option("server", "fact-resource-block", 60,
           "Minimal time between subsequent requests for the same fact", is_time)

server_autrecompile_wait = \
    Option("server", "auto-recompile-wait ", 10,
           """The number of seconds to wait before the server may attempt to do a new recompile.
           Recompiles are triggered after facts updates for example.""", is_time)

server_purge_version_interval = \
    Option("server", "purge-versions-interval", 3600,
           """The number of seconds between version purging,
see :inmanta.config:option:`server.available-versions-to-keep`""", is_time)

server_version_to_keep = \
    Option("server", "available-versions-to-keep", 2,
           """On boot and at regular intervals the server will purge versions that have not been deployed.
This is the number of most recent undeployed versions to keep available.""", is_int)

server_autostart_on_start = \
    Option("server", "autostart-on-start", True,
           "Automatically start agents when the server starts instead of only just in time.", is_bool)

server_agent_autostart = \
    Option("server", "agent-autostart", "iaas_*",
           """Which agents can the server start itself?
Setting this value to * will match all agents.
These agents are started when a dryrun or a deploy is requested.""", is_list)

server_address = \
    Option("server", "server_address", "localhost",
           """The public ip address of the server.
This is required for example to inject the inmanta agent in virtual machines at boot time.""")

server_wait_after_param = \
    Option("server", "wait-after-param", 5,
           """Time to wait before recompile after new paramters have been received""", is_time)

server_no_recompile = \
    Option("server", "no-recompile", False,
           """Prevent all server side compiles""", is_bool)

#############################
# Dashboard
#############################

dash_enable = \
    Option("dashboard", "enabled", False,
           "Determines whether the server should host the dashboard or not", is_bool)

dash_path = \
    Option("dashboard", "path", None,
           "The path on the local file system where the dashboard can be found")

timeout = \
    Option("config", "timout", 2,
           "Timeout for agent calls from server to agent", is_time)