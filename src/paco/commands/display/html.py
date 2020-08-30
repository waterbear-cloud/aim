import os
import pathlib
from chameleon import PageTemplateLoader
from paco.models.references import get_model_obj_from_ref




def display_project_as_html(project):
    path = os.path.dirname(__file__)
    static_path = pathlib.Path(path) / 'static'
    templates = PageTemplateLoader(path)
    userinfo = project.credentials

    def resolve_ref(ref_string):
        return get_model_obj_from_ref(ref_string, project)

    # Project
    project_tmpl = templates['project.pt']
    # Environments
    envs_html = {}
    env_tmpl = templates['env.pt']
    for netenv in project['netenv'].values():
        for env in netenv.values():
            envs_html[f'ne-{netenv.name}-{env.name}.html'] = env_tmpl(
                project=project,
                netenv=netenv,
                env=env,
                userinfo=userinfo,
                templates=templates,
            )
    project_html = project_tmpl(
        project=project,
        userinfo=userinfo,
        resolve_ref=resolve_ref,
        templates=templates,
    )
    return static_path, project_html, envs_html
