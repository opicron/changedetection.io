import threading
from flask import Blueprint, request, render_template, flash, url_for, redirect
from flask_babel import gettext
from loguru import logger

from changedetectionio.store import ChangeDetectionStore
from changedetectionio.flask_app import login_optionally_required


def construct_blueprint(datastore: ChangeDetectionStore):
    tags_blueprint = Blueprint('tags', __name__, template_folder="templates")

    @tags_blueprint.route("/list", methods=['GET'])
    @login_optionally_required
    def tags_overview_page():
        from .form import SingleTag
        add_form = SingleTag(request.form)

        sorted_tags = sorted(datastore.data['settings']['application'].get('tags').items(), key=lambda x: x[1]['title'])

        from collections import Counter

        tag_count = Counter(tag for watch in datastore.data['watching'].values() if watch.get('tags') for tag in watch['tags'])

        output = render_template("groups-overview.html",
                                 app_rss_token=datastore.data['settings']['application'].get('rss_access_token'),
                                 available_tags=sorted_tags,
                                 form=add_form,
                                 tag_count=tag_count,
                                 )

        return output

    @tags_blueprint.route("/add", methods=['POST'])
    @login_optionally_required
    def form_tag_add():
        from .form import SingleTag
        add_form = SingleTag(request.form)

        if not add_form.validate():
            for widget, l in add_form.errors.items():
                flash(','.join(l), 'error')
            return redirect(url_for('tags.tags_overview_page'))

        title = request.form.get('name').strip()

        if datastore.tag_exists_by_name(title):
            flash(gettext('The tag "{}" already exists').format(title), "error")
            return redirect(url_for('tags.tags_overview_page'))

        datastore.add_tag(title)
        flash(gettext("Tag added"))


        return redirect(url_for('tags.tags_overview_page'))

    @tags_blueprint.route("/mute/<string:uuid>", methods=['GET'])
    @login_optionally_required
    def mute(uuid):
        if datastore.data['settings']['application']['tags'].get(uuid):
            datastore.data['settings']['application']['tags'][uuid]['notification_muted'] = not datastore.data['settings']['application']['tags'][uuid]['notification_muted']
        return redirect(url_for('tags.tags_overview_page'))

    @tags_blueprint.route("/delete/<string:uuid>", methods=['GET'])
    @login_optionally_required
    def delete(uuid):
        # Delete the tag from settings immediately
        if datastore.data['settings']['application']['tags'].get(uuid):
            del datastore.data['settings']['application']['tags'][uuid]

        # Remove tag from all watches in background thread to avoid blocking
        def remove_tag_background(tag_uuid):
            """Background thread to remove tag from watches - discarded after completion."""
            removed_count = 0
            try:
                for watch_uuid, watch in datastore.data['watching'].items():
                    if watch.get('tags') and tag_uuid in watch['tags']:
                        watch['tags'].remove(tag_uuid)
                        removed_count += 1
                logger.info(f"Background: Tag {tag_uuid} removed from {removed_count} watches")
            except Exception as e:
                logger.error(f"Error removing tag from watches: {e}")

        # Start daemon thread
        threading.Thread(target=remove_tag_background, args=(uuid,), daemon=True).start()

        flash(gettext("Tag deleted, removing from watches in background"))
        return redirect(url_for('tags.tags_overview_page'))

    @tags_blueprint.route("/unlink/<string:uuid>", methods=['GET'])
    @login_optionally_required
    def unlink(uuid):
        # Unlink tag from all watches in background thread to avoid blocking
        def unlink_tag_background(tag_uuid):
            """Background thread to unlink tag from watches - discarded after completion."""
            unlinked_count = 0
            try:
                for watch_uuid, watch in datastore.data['watching'].items():
                    if watch.get('tags') and tag_uuid in watch['tags']:
                        watch['tags'].remove(tag_uuid)
                        unlinked_count += 1
                logger.info(f"Background: Tag {tag_uuid} unlinked from {unlinked_count} watches")
            except Exception as e:
                logger.error(f"Error unlinking tag from watches: {e}")

        # Start daemon thread
        threading.Thread(target=unlink_tag_background, args=(uuid,), daemon=True).start()

        flash(gettext("Unlinking tag from watches in background"))
        return redirect(url_for('tags.tags_overview_page'))

    @tags_blueprint.route("/delete_all", methods=['GET'])
    @login_optionally_required
    def delete_all():
        # Clear all tags from settings immediately
        datastore.data['settings']['application']['tags'] = {}

        # Clear tags from all watches in background thread to avoid blocking
        def clear_all_tags_background():
            """Background thread to clear tags from all watches - discarded after completion."""
            cleared_count = 0
            try:
                for watch_uuid, watch in datastore.data['watching'].items():
                    watch['tags'] = []
                    cleared_count += 1
                logger.info(f"Background: Cleared tags from {cleared_count} watches")
            except Exception as e:
                logger.error(f"Error clearing tags from watches: {e}")

        # Start daemon thread
        threading.Thread(target=clear_all_tags_background, daemon=True).start()

        flash(gettext("All tags deleted, clearing from watches in background"))
        return redirect(url_for('tags.tags_overview_page'))

    @tags_blueprint.route("/edit/<string:uuid>", methods=['GET'])
    @login_optionally_required
    def form_tag_edit(uuid):
        from changedetectionio.blueprint.tags.form import group_restock_settings_form, group_request_settings_form
        if uuid == 'first':
            uuid = list(datastore.data['settings']['application']['tags'].keys()).pop()

        default = datastore.data['settings']['application']['tags'].get(uuid)
        if not default:
            flash(gettext("Tag not found"), "error")
            return redirect(url_for('watchlist.index'))

        restock_form = group_restock_settings_form(
                                       formdata=request.form if request.method == 'POST' else None,
                                       data=default,
                                       extra_notification_tokens=datastore.get_unique_notification_tokens_available(),
                                       default_system_settings = datastore.data['settings'],
                                       )

        request_form = group_request_settings_form(
                                       formdata=request.form if request.method == 'POST' else None,
                                       data=default,
                                       extra_notification_tokens=datastore.get_unique_notification_tokens_available(),
                                       default_system_settings = datastore.data['settings'],
                                       )

        template_args = {
            'data': default,
            'form': restock_form,
            'request_form': request_form,
            'watch': default,
            'extra_notification_token_placeholder_info': datastore.get_unique_notification_token_placeholders_available(),
        }

        # TODO: Set up proxy choices for the request settings form (temporarily disabled for testing)
        # if datastore.proxy_list is not None and hasattr(form, 'request_settings') and hasattr(form.request_settings.form, 'proxy'):
        #     form.request_settings.form.proxy.choices = [('', 'Default')]
        #     for p in datastore.proxy_list:
        #         form.request_settings.form.proxy.choices.append(tuple((p, datastore.proxy_list[p]['label'])))
        # elif hasattr(form, 'request_settings') and hasattr(form.request_settings.form, 'proxy'):
        #     # Remove proxy field if no proxies are configured
        #     delattr(form.request_settings.form, 'proxy')

        included_content = {}
        if restock_form.extra_form_content():
            # So that the extra panels can access _helpers.html etc, we set the environment to load from templates/
            # And then render the code from the module
            from jinja2 import Environment, FileSystemLoader
            import importlib.resources
            templates_dir = str(importlib.resources.files("changedetectionio").joinpath('templates'))
            env = Environment(loader=FileSystemLoader(templates_dir))
            template_str = """{% from '_helpers.html' import render_field, render_checkbox_field, render_button %}
        <script>        
            $(document).ready(function () {
                toggleOpacity('#overrides_watch', '#restock-fieldset-price-group', true);
                toggleOpacity('#request_overrides_watch', '#request-fieldset-group', true);
            });
        </script>            
                <fieldset>
                    <div class="pure-control-group">
                        <fieldset class="pure-group">
                        {{ render_checkbox_field(form.overrides_watch) }}
                        <span class="pure-form-message-inline">Used for watches in "Restock & Price detection" mode</span>
                        </fieldset>
                </fieldset>
                """
            template_str += restock_form.extra_form_content()
            template = env.from_string(template_str)
            included_content = template.render(**template_args)

        # Generate request form content
        request_content = ""
        if request_form.extra_form_content():
            from jinja2 import Environment, FileSystemLoader
            import importlib.resources
            templates_dir = str(importlib.resources.files("changedetectionio").joinpath('templates'))
            request_env = Environment(loader=FileSystemLoader(templates_dir))
            request_template_str = """{% from '_helpers.html' import render_field, render_checkbox_field, render_button %}
                <fieldset>
                    <div class="pure-control-group">
                        <fieldset class="pure-group">
                        {{ render_checkbox_field(form.request_overrides_watch) }}
                        <span class="pure-form-message-inline">Used for request settings (headers, body, method, proxy) in all watch modes</span>
                        </fieldset>
                </fieldset>
                """
            request_template_str += request_form.extra_form_content()
            request_template = request_env.from_string(request_template_str)
            # Create template args for request form
            request_template_args = {
                'data': default,
                'form': request_form,
                'request_form': request_form,
                'watch': default,
                'extra_notification_token_placeholder_info': datastore.get_unique_notification_token_placeholders_available(),
            }
            request_content = request_template.render(**request_template_args)

        output = render_template("edit-tag.html",
                                 extra_form_content=included_content,
                                 request_form_content=request_content,
                                 extra_tab_content=restock_form.extra_tab_content() if restock_form.extra_tab_content() else None,
                                 settings_application=datastore.data['settings']['application'],
                                 **template_args
                                 )

        return output


    @tags_blueprint.route("/edit/<string:uuid>", methods=['POST'])
    @login_optionally_required
    def form_tag_edit_submit(uuid):
        from changedetectionio.blueprint.tags.form import group_restock_settings_form, group_request_settings_form
        if uuid == 'first':
            uuid = list(datastore.data['settings']['application']['tags'].keys()).pop()

        default = datastore.data['settings']['application']['tags'].get(uuid)

        restock_form = group_restock_settings_form(formdata=request.form if request.method == 'POST' else None,
                               data=default,
                               extra_notification_tokens=datastore.get_unique_notification_tokens_available()
                               )
        
        request_form = group_request_settings_form(formdata=request.form if request.method == 'POST' else None,
                               data=default,
                               extra_notification_tokens=datastore.get_unique_notification_tokens_available()
                               )
        
        # Setup proxy choices for request form
        if datastore.proxy_list is not None and hasattr(request_form, 'request_settings') and hasattr(request_form.request_settings.form, 'proxy'):
            request_form.request_settings.form.proxy.choices = [('', 'Default')]
            for p in datastore.proxy_list:
                request_form.request_settings.form.proxy.choices.append(tuple((p, datastore.proxy_list[p]['label'])))
        elif hasattr(request_form, 'request_settings') and hasattr(request_form.request_settings.form, 'proxy'):
            # Remove proxy field if no proxies are configured
            delattr(request_form.request_settings.form, 'proxy')
            
        # @todo subclass form so validation works
        #if not form.validate():
#            for widget, l in form.errors.items():
#                flash(','.join(l), 'error')
#           return redirect(url_for('tags.form_tag_edit_submit', uuid=uuid))

        # Update tag data with both forms
        datastore.data['settings']['application']['tags'][uuid].update(restock_form.data)
        datastore.data['settings']['application']['tags'][uuid].update(request_form.data)
        datastore.data['settings']['application']['tags'][uuid]['processor'] = 'restock_diff'
        datastore.needs_write_urgent = True
        flash(gettext("Updated"))

        return redirect(url_for('tags.tags_overview_page'))


    @tags_blueprint.route("/delete/<string:uuid>", methods=['GET'])
    def form_tag_delete(uuid):
        return redirect(url_for('tags.tags_overview_page'))
    return tags_blueprint
