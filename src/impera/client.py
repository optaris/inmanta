"""
    Copyright 2015 Impera

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

    Contact: bart@impera.io

    This module contains a client to communicate with Impera agents and other
    services connected to the Impera message bus.
"""

from collections import defaultdict
import logging

from impera import protocol
from cliff.lister import Lister
from cliff.show import ShowOne
from cliff.command import Command
from impera.config import Config
from blessings import Terminal
import uuid

LOGGER = logging.getLogger(__name__)


def client_parser(parser):
    parser.add_argument("--host", dest="host", help="The server hostname to connect to (default: localhost)",
                        default="localhost")
    parser.add_argument("--port", dest="port", help="The server port to connect to (default: 8888)", default=8888, type=int)


class ImperaCommand(Command):
    """
        An impera command
    """
    log = logging.getLogger(__name__)

    def __init__(self, app, app_args):
        super().__init__(app, app_args)
        self._client = None

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        Config.load_config()

        parser.add_argument("--host", dest="host", help="The server hostname to connect to (default: localhost)",
                            default=Config.get("cmdline_rest_transport", "host", "localhost"))
        parser.add_argument("--port", dest="port", help="The server port to connect to (default: 8888)",
                            default=int(Config.get("cmdline_rest_transport", "port", 8888)), type=int)
        parser = self.parser_config(parser)
        return parser

    def parser_config(self, parser):
        """
            Method for a subclass to override to add additional arguments to the command
        """
        return parser

    def do_request(self, method_name, key_name=None, arguments={}):
        """
            Do a request and return the response
        """
        type(self).log.debug("Calling method %s on server %s:%s with arguments %s" %
                             (method_name, Config.get("cmdline_rest_transport", "host"),
                              Config.get("cmdline_rest_transport", "port"), arguments))

        if not hasattr(self._client, method_name):
            raise Exception("API call %s is not available." % method_name)

        method = getattr(self._client, method_name)

        result = method(**arguments)

        if result is None:
            raise Exception("Failed to call server.")

        type(self).log.debug("Got response code %s and data: %s" % (result.code, result.result))

        if result.code == 200:
            if key_name is None:
                return result.result

            if key_name in result.result:
                return result.result[key_name]

            raise Exception("Expected %s in the response of %s." % (key_name, method_name))
        elif result.code == 404:
            raise Exception("Requested %s not found on server" % key_name)

        else:
            msg = ": "
            if result.result is not None and "message" in result.result:
                msg += result.result["message"]

            raise Exception(("An error occurred while requesting %s" % key_name) + msg)

    def to_project_id(self, ref):
        """
            Convert ref to a uuid
        """
        try:
            project_id = uuid.UUID(ref)
        except ValueError:
            # try to resolve the id as project name
            projects = self.do_request("list_projects", "projects")

            id_list = []
            for project in projects:
                if ref == project["name"]:
                    id_list.append(project["id"])

            if len(id_list) == 0:
                raise Exception("Unable to find a project with the given id or name")

            elif len(id_list) > 1:
                raise Exception("Found multiple projects with %s name, please use the ID." % ref)

            else:
                project_id = id_list[0]

        return project_id

    def take_action(self, parsed_args):
        self._client = protocol.Client("cmdline", "client")
        return self.run_action(parsed_args)

    def run_action(self, parsed_args):
        raise NotImplementedError()


class ProjectShow(ImperaCommand, ShowOne):
    """
        Show project details
    """
    def parser_config(self, parser):
        parser.add_argument("id", help="The the id of the project to show")
        return parser

    def run_action(self, parsed_args):
        project_id = self.to_project_id(parsed_args.id)
        project = self.do_request("get_project", "project", dict(id=project_id))
        return (('ID', 'Name'), ((project["id"], project["name"])))


class ProjectCreate(ImperaCommand, ShowOne):
    """
        Create a new project
    """
    def parser_config(self, parser):
        parser.add_argument("-n", "--name", dest="name", help="The name of the new project")
        return parser

    def run_action(self, parsed_args):
        project = self.do_request("create_project", "project", {"name": parsed_args.name})
        return (('ID', 'Name'), ((project["id"], project["name"])))


class ProjectModify(ImperaCommand, ShowOne):
    """
        Modify a project
    """
    def parser_config(self, parser):
        parser.add_argument("-n", "--name", dest="name", help="The name of the new project")
        parser.add_argument("id", help="The id of the project to modify")
        return parser

    def run_action(self, parsed_args):
        project_id = self.to_project_id(parsed_args.id)
        project = self.do_request("modify_project", "project", dict(id=project_id, name=parsed_args.name))

        return (('ID', 'Name'), ((project["id"], project["name"])))


class ProjectList(ImperaCommand, Lister):
    """
        List all projects defined on the server
    """
    def run_action(self, parsed_args):
        projects = self.do_request("list_projects", "projects")

        if len(projects) > 0:
            return (('ID', 'Name'), ((n['id'], n['name']) for n in projects))

        print("No projects defined.")
        return ((), ())


class ProjectDelete(ImperaCommand, Command):
    """
        Delete a project
    """
    def parser_config(self, parser):
        parser.add_argument("id", help="The id of the project to delete.")
        return parser

    def run_action(self, parsed_args):
        project_id = self.to_project_id(parsed_args.id)
        self.do_request("delete_project", arguments={"id": project_id})
        print("Project successfully deleted", file=self.app.stdout)


class EnvironmentCreate(ShowOne):
    """
        Create a new environment
    """
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        client_parser(parser)
        parser.add_argument("-n", "--name", dest="name", help="The name of the new environment")
        parser.add_argument("-p", "--project", dest="project", help="The id of the project this environment belongs to")
        parser.add_argument("-r", "--repo-url", dest="repo",
                            help="The url of the repository that contains the configuration model")
        parser.add_argument("-b", "--branch", dest="branch",
                            help="The branch in the repository that contains the configuration model")
        return parser

    def take_action(self, parsed_args):
        Config.load_config()
        Config.set("cmdline_rest_transport", "host", parsed_args.host)
        Config.set("cmdline_rest_transport", "port", str(parsed_args.port))
        client = protocol.Client("cmdline", "client")

        result = client.create_environment(project_id=parsed_args.project, name=parsed_args.name, repository=parsed_args.repo,
                                           branch=parsed_args.branch)

        if result.code == 200:
            project = client.get_project(id=parsed_args.project)

            if result.code != 200:
                print("Failed to fetch project details.")
                project_name = "err..."

            else:
                project_name = project.result["name"]

            return (('Environment ID', 'Environment name', 'Project ID', 'Project name'),
                    ((result.result["id"], result.result["name"], parsed_args.project, project_name))
                    )
        else:
            print("Failed to create environment: " + result.result["message"], file=self.app.stderr)
            return ((), ())


class EnvironmentList(ImperaCommand, Lister):
    """
        List environment defined on the server
    """
    def run_action(self, parsed_args):
        result = self._client.list_environments()

        if result.code == 200:
            data = []
            for env in result.result["environments"]:
                prj = self._client.get_project(id=env["project"])
                if prj.code != 200:
                    print("Unable to fetch project details")
                    prj_name = "?"
                else:
                    prj_name = prj.result["project"]['name']

                data.append((prj_name, env['project'], env['name'], env['id']))

            if len(data) > 0:
                return (('Project name', 'Project ID', 'Environment', 'Environment ID'), data)

            print("No environment defined.")
            return ((), ())
        else:
            print("Failed to list environments: " + result.result["message"], file=self.app.stderr)
            return ((), ())


class EnvironmentShow(ShowOne):
    """
        Show environment details
    """
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        client_parser(parser)
        parser.add_argument("id", help="The the id of the evironment to show")
        return parser

    def take_action(self, parsed_args):
        Config.load_config()
        Config.set("cmdline_rest_transport", "host", parsed_args.host)
        Config.set("cmdline_rest_transport", "port", str(parsed_args.port))
        client = protocol.Client("cmdline", "client")

        result = client.get_environment(id=parsed_args.id)

        if result.code == 200:
            return (('ID', 'Name', 'Repository URL', 'Branch Name'),
                    ((result.result["id"],
                      result.result["name"],
                      result.result["repo_url"] if "repo_url" in result.result else "",
                      result.result["repo_branch"] if "repo_branch" in result.result else ""))
                    )
        else:
            print("Failed to get environment: " + result.result["message"], file=self.app.stderr)
            return ((), ())


class EnvironmentModify(ShowOne):
    """
        Modify an environment
    """
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        client_parser(parser)
        parser.add_argument("-n", "--name", dest="name", help="The name of the environment")
        parser.add_argument("id", help="The id of the environment to modify")
        parser.add_argument("-r", "--repo-url", dest="repo",
                            help="The url of the repository that contains the configuration model")
        parser.add_argument("-b", "--branch", dest="branch",
                            help="The branch in the repository that contains the configuration model")
        return parser

    def take_action(self, parsed_args):
        Config.load_config()
        Config.set("cmdline_rest_transport", "host", parsed_args.host)
        Config.set("cmdline_rest_transport", "port", str(parsed_args.port))
        client = protocol.Client("cmdline", "client")

        result = client.modify_environment(id=parsed_args.id, name=parsed_args.name, repository=parsed_args.repo,
                                           branch=parsed_args.branch)

        if result.code == 200:
            return (('ID', 'Name', 'Repository URL', 'Branch Name'),
                    ((result.result["id"],
                      result.result["name"],
                      result.result["repo_url"] if "repo_url" in result.result else "",
                      result.result["repo_branch"] if "repo_branch" in result.result else ""))
                    )
        else:
            print("Failed to modify project: " + result.result["message"], file=self.app.stderr)
            return ((), ())


class EnvironmentDelete(Command):
    """
        Delete an environment
    """
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        client_parser(parser)
        parser.add_argument("id", help="The id of the environment to delete.")
        return parser

    def take_action(self, parsed_args):
        Config.load_config()
        Config.set("cmdline_rest_transport", "host", parsed_args.host)
        Config.set("cmdline_rest_transport", "port", str(parsed_args.port))
        client = protocol.Client("cmdline", "client")

        result = client.delete_environment(id=parsed_args.id)

        if result.code == 200:
            print("Environment successfully deleted", file=self.app.stdout)
        else:
            print("Failed to delete environment: " + result.result["message"], file=self.app.stderr)


class VersionList(Lister):
    """
        List the configuration model versions
    """
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        client_parser(parser)
        parser.add_argument("-e", "--environment", dest="env", help="The id of environment")
        return parser

    def take_action(self, parsed_args):
        Config.load_config()
        Config.set("cmdline_rest_transport", "host", parsed_args.host)
        Config.set("cmdline_rest_transport", "port", str(parsed_args.port))
        client = protocol.Client("cmdline", "client")

        if parsed_args.env is None:
            print("The environment is a required argument.", file=self.app.stderr)
            return ((), ())

        result = client.list_versions(tid=parsed_args.env)

        if result.code == 200:
            return (('Created at', 'Version', 'Release status'),
                    ((x['date'], x['version'], x['release_status']) for x in result.result["versions"])
                    )
        else:
            print("Failed to list environments: " + result.result["message"], file=self.app.stderr)
            return ((), ())


class AgentList(Lister):
    """
        List all the agents connected to the server
    """
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        client_parser(parser)
        return parser

    def take_action(self, parsed_args):
        Config.load_config()
        Config.set("cmdline_rest_transport", "host", parsed_args.host)
        Config.set("cmdline_rest_transport", "port", str(parsed_args.port))
        client = protocol.Client("cmdline", "client")

        result = client.list_agents()

        if result.code == 200:
            data = []
            for node in result.result["nodes"]:
                for agent in node["agents"]:
                    data.append((node["hostname"], agent["name"], agent["role"], agent["environment"], node["last_seen"]))

            return (('Node', 'Agent', 'Role', 'Environment', 'Last seen'), data)
        else:
            print("Failed to list agents: " + result.result["message"], file=self.app.stderr)
            return ((), ())


class VersionRelease(ShowOne):
    """
        Release a version of the configuration model
    """
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        client_parser(parser)
        parser.add_argument("-e", "--environment", dest="env", help="The id of environment")
        parser.add_argument("-n", "--dry-run", dest="dryrun", action="store_true", help="Request a dry run deploy")
        parser.add_argument("-p", "--push", dest="push", action="store_true", help="Push the version to the deployment agents")
        parser.add_argument("version", help="The version to release for deploy")
        return parser

    def take_action(self, parsed_args):
        Config.load_config()
        Config.set("cmdline_rest_transport", "host", parsed_args.host)
        Config.set("cmdline_rest_transport", "port", str(parsed_args.port))
        client = protocol.Client("cmdline", "client")

        if parsed_args.env is None:
            print("The environment is a required argument.", file=self.app.stderr)
            return ((), ())

        if parsed_args.version is None:
            print("The version is a required argument.", file=self.app.stderr)
            return ((), ())

        result = client.release_version(tid=parsed_args.env, id=parsed_args.version, dryrun=parsed_args.dryrun,
                                        push=parsed_args.push)

        if result.code == 200:
            x = result.result
            return (('Created at', 'Version', 'Release status'),
                    ((x['date'], x['version'], x['release_status']))
                    )
        else:
            print("Failed to release configuration model version: " + result.result["message"], file=self.app.stderr)
            return ((), ())


class ParamList(Lister):
    """
        List all parameters for the environment
    """
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        client_parser(parser)
        parser.add_argument("-e", "--environment", dest="env", help="The id of environment")
        return parser

    def take_action(self, parsed_args):
        Config.load_config()
        Config.set("cmdline_rest_transport", "host", parsed_args.host)
        Config.set("cmdline_rest_transport", "port", str(parsed_args.port))
        client = protocol.Client("cmdline", "client")

        if parsed_args.env is None:
            print("The environment is a required argument.", file=self.app.stderr)
            return ((), ())

        result = client.list_params(parsed_args.env)

        if result.code == 200:
            data = []
            for p in result.result:
                data.append((p["resource_id"], p['name'], p['source'], p['updated']))

            return (('Resource', 'Name', 'Source', 'Updated'), data)
        else:
            print("Failed to list parameters: " + result.result["message"], file=self.app.stderr)
            return ((), ())


class ParamSet(ShowOne):
    """
        Set a parameter in the environment
    """
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        client_parser(parser)
        parser.add_argument("-e", "--environment", dest="env", help="The id of environment")
        parser.add_argument("--name", dest="name", help="The name of the parameter")
        parser.add_argument("--value", dest="value", help="The value of the parameter")
        return parser

    def take_action(self, parsed_args):
        Config.load_config()
        Config.set("cmdline_rest_transport", "host", parsed_args.host)
        Config.set("cmdline_rest_transport", "port", str(parsed_args.port))
        client = protocol.Client("cmdline", "client")

        if parsed_args.env is None:
            print("The environment is a required argument.", file=self.app.stderr)
            return ((), ())

        if parsed_args.name is None:
            print("The parameter name is a required argument.", file=self.app.stderr)
            return ((), ())

        if parsed_args.value is None:
            print("The parameter value is a required argument.", file=self.app.stderr)
            return ((), ())

        # first fetch the parameter
        result = client.get_param(tid=parsed_args.env, id=parsed_args.name, resource_id="")
        if result.code == 200:
            # check the source
            if result.result["source"] != "user":
                print("Only parameters set by users can be modified!", file=self.app.stderr)

                return ((), ())

        result = client.set_param(tid=parsed_args.env, id=parsed_args.name, value=parsed_args.value, source="user",
                                  resource_id="")

        if result.code == 200:
            return (('Name', 'Value', 'Source', 'Updated'),
                    (result.result['name'], result.result['value'], result.result['source'], result.result['updated']))
        else:
            print("Failed to list parameters: " + result.result["message"], file=self.app.stderr)
            return ((), ())


class ParamGet(ShowOne):
    """
        Set a parameter in the environment
    """
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        client_parser(parser)
        parser.add_argument("-e", "--environment", dest="env", help="The id of environment")
        parser.add_argument("--name", dest="name", help="The name of the parameter")
        parser.add_argument("--resource", dest="resource", help="The resource id of the parameter")
        return parser

    def take_action(self, parsed_args):
        Config.load_config()
        Config.set("cmdline_rest_transport", "host", parsed_args.host)
        Config.set("cmdline_rest_transport", "port", str(parsed_args.port))
        client = protocol.Client("cmdline", "client")

        if parsed_args.env is None:
            print("The environment is a required argument.", file=self.app.stderr)
            return ((), ())

        if parsed_args.name is None:
            print("The parameter name is a required argument.", file=self.app.stderr)
            return ((), ())

        resource = parsed_args.resource
        if resource is None:
            resource = ""

        # first fetch the parameter
        result = client.get_param(tid=parsed_args.env, id=parsed_args.name, resource_id=resource)

        if result.code == 200:
            return (('Name', 'Value', 'Source', 'Updated'),
                    (result.result['name'], result.result['value'], result.result['source'], result.result['updated']))

        elif result.code == 503:
            print("Parameter not available, facts about resource requested from managing agent.", file=self.app.stderr)
            return ((), ())

        else:
            print("Failed to get parameter: " + result.result["message"], file=self.app.stderr)
            return ((), ())


class VersionReport(Command):
    """
        Create a dryrun or deploy report from a version
    """
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(VersionReport, self).get_parser(prog_name)
        client_parser(parser)
        parser.add_argument("-e", "--environment", dest="env", help="The id of environment")
        parser.add_argument("-i", "--version", dest="version", help="The version to create a report from")
        parser.add_argument("-l", dest="details", action="store_true", help="Show a detailed version of the report")
        parser.add_argument("release", help="Create the report from a dryrun or deploy")
        return parser

    def take_action(self, parsed_args):
        Config.load_config()
        Config.set("cmdline_rest_transport", "host", parsed_args.host)
        Config.set("cmdline_rest_transport", "port", str(parsed_args.port))
        client = protocol.Client("cmdline", "client")

        if parsed_args.env is None:
            print("The environment is a required argument.", file=self.app.stderr)
            return ((), ())

        if parsed_args.version is None:
            print("The version is a required argument.", file=self.app.stderr)
            return ((), ())

        if parsed_args.release != "deploy" and parsed_args.release != "dryrun":
            print("Only deploy or dryrun reports can be created.", file=self.app.stderr)
            return

        result = client.get_version(tid=parsed_args.env, id=parsed_args.version, include_logs=True,
                                    log_filter=parsed_args.release)

        if result.code == 200:
            term = Terminal()
            agents = defaultdict(lambda: defaultdict(lambda: []))
            for res in result.result["resources"]:
                if (len(res["actions"]) > 0 and len(res["actions"][0]["data"]) > 0) or parsed_args.details:
                    agents[res["id_fields"]["agent_name"]][res["id_fields"]["entity_type"]].append(res)

            for agent in sorted(agents.keys()):
                print(term.bold("Agent: %s" % agent))
                print("=" * 72)

                for type in sorted(agents[agent].keys()):
                    print("{t.bold}Resource type:{t.normal} {type} ({attr})".
                          format(type=type, attr=agents[agent][type][0]["id_fields"]["attribute"], t=term))
                    print("-" * 72)

                    for res in agents[agent][type]:
                        print((term.bold + "%s" + term.normal + " (state=%s, last_result=%s, #actions=%d)") %
                              (res["id_fields"]["attribute_value"], res["state"], res["result"], len(res["actions"])))
                        # for dryrun show only the latest, for deploy all
                        if parsed_args.release == "dryrun":
                            if len(res["actions"]) > 0:
                                action = res["actions"][0]
                                print("* last check: %s" % action["timestamp"])
                                print("* result: %s" % ("error" if action["level"] != "INFO" else "success"))
                                if len(action["data"]) == 0:
                                    print("* no changes")
                                else:
                                    print("* changes:")
                                    for field in sorted(action["data"].keys()):
                                        values = action["data"][field]
                                        if field == "hash":
                                            print("  - content:")
                                            diff_value = client.diff(values[0], values[1]).result
                                            print("    " + "    ".join(diff_value["diff"]))
                                        else:
                                            print("  - %s:" % field)
                                            print("    " + term.bold + "from:" + term.normal + " %s" % values[0])
                                            print("    " + term.bold + "to:" + term.normal + " %s" % values[1])

                                        print("")

                                print("")
                        else:
                            pass

                    print("")
        else:
            print("Failed to get a report for configuration model version: " + result.result["message"], file=self.app.stderr)
