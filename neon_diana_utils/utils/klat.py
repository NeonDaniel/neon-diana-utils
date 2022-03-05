# NEON AI (TM) SOFTWARE, Software Development Kit & Application Development System
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2021 Neongecko.com Inc.
# BSD-3
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from this
#    software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS;  OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE,  EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import json

from os import makedirs
from os.path import expanduser, isdir, isfile, dirname, join
from click import prompt
from ruamel.yaml import YAML
from neon_utils.logger import LOG

from neon_diana_utils.utils.docker_utils import write_docker_compose
from neon_diana_utils.utils.kubernetes_utils import generate_config_map, write_kubernetes_spec


def cli_configure_klat(output_path: str, server_external_url: str,
                       mongodb_url: str, mongodb_port: int,
                       mongodb_username: str, mongodb_password: str,
                       namespace: str):
    """
    Build a config.json file for a Klat server.
    :param output_path: config output directory
    :param server_external_url: Accessible URL for the Klat server module
    :param mongodb_url: Server-accessible URL or IP address for MongoDB
    :param mongodb_port: Port used to connect to MongoDB
    :param mongodb_username: Configured MongoDB user for server operations
    :param mongodb_password: Password associated with mongodb_username
    :param namespace: Kubernetes namespace to configure
    """
    if not output_path:
        raise ValueError("Null output_path specified")
    output_path = expanduser(output_path)
    if isfile(output_path):
        raise FileExistsError(f"Specified output path is a file")
    if not isdir(output_path):
        makedirs(output_path)

    server_external_url = server_external_url or \
        prompt("External URL (i.e. http://api.klat.com)",
               default="http://localhost:8010")
    mongodb_url = mongodb_url or prompt("MongoDB URL (i.e. mongo.klat.com)")
    mongodb_port = mongodb_port or prompt("MongoDB Port", default=27017)
    mongodb_username = mongodb_username or prompt("MongoDB username")
    mongodb_password = mongodb_password or prompt("MongoDB password")
    namespace = namespace or "default"
    config = build_klat_config(join(output_path, "config.json"),
                               server_external_url, mongodb_url,
                               mongodb_port, mongodb_username,
                               mongodb_password)
    generate_config_map("klat", {"config.json": json.dumps(config)},
                        join(output_path, "k8s_klat_config.yml"))
    compose, kubernetes = _get_klat_services_config()
    write_docker_compose(compose, join(output_path, "docker-compose.yml"),
                         volumes={"config": output_path})
    write_kubernetes_spec(kubernetes, output_path,
                          {"KLAT_NAMESPACE": namespace}, "k8s_klat.yml")
    return output_path


def build_klat_config(output_file: str, server_external_url: str,
                      mongodb_url: str, mongodb_port: int,
                      mongodb_username: str, mongodb_password: str) -> dict:
    """
    Build a config.json file to use with Klat modules
    :param output_file: file path to write
    :param server_external_url: Accessible URL for the Klat server module
    :param mongodb_url: Server-accessible URL or IP address for MongoDB
    :param mongodb_port: Port used to connect to MongoDB
    :param mongodb_username: Configured MongoDB user for server operations
    :param mongodb_password: Password associated with mongodb_username
    :returns: parsed configuration
    """
    if not mongodb_username:
        raise ValueError("No MongoDB username specified")
    if not mongodb_password:
        raise ValueError("No MongoDB password specified")
    if not output_file:
        raise ValueError("No output_file specified")
    output_file = expanduser(output_file)
    if isfile(output_file):
        raise FileExistsError(f"File already exists: {output_file}")
    makedirs(dirname(output_file), exist_ok=True)
    server_external_url = server_external_url or "http://localhost:8010"
    mongodb_url = mongodb_url or "localhost"
    mongodb_port = mongodb_port or 27017

    template_file = join(dirname(dirname(__file__)),
                         "templates", "klat_config.yml")

    with open(template_file) as f:
        template_contents = f.read()

    template_contents = \
        template_contents.replace(
            "${SOCKET_HTTP_URL}", server_external_url).replace(
            "${MONGO_DB_URL}", mongodb_url).replace(
            "${MONGO_DB_PORT}", str(mongodb_port)).replace(
            "${MONGO_USER}", mongodb_username).replace(
            "${MONGO_PASS}", mongodb_password)

    config_data = YAML().load(template_contents)
    LOG.debug(f"config_data={json.dumps(config_data)}")
    with open(output_file, 'w') as f:
        json.dump(config_data, f, indent=2)
    return json.loads(json.dumps(config_data))


def _get_klat_services_config() -> (dict, list):
    """
    Parse Klat services from service_mappings.yml
    :returns: docker_compose spec, kubernetes spec
    """

    template_file = join(dirname(dirname(__file__)), "templates",
                         "service_mappings.yml")
    with open(template_file) as f:
        template_data = YAML().load(f)
    services_to_configure = {name: dict(template_data[name])
                             for name in template_data if
                             template_data[name]["service_class"] == "klat"}
    docker_compose = dict()
    kubernetes_spec = list()
    for service in services_to_configure:
        docker_compose[service] = \
            services_to_configure[service]["docker_compose"]
        kubernetes_spec.extend(
            services_to_configure[service].get("kubernetes", []))

    return docker_compose, kubernetes_spec
