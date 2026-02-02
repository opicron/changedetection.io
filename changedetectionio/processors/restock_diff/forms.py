from wtforms import (
    BooleanField,
    validators,
    FloatField,
    SelectField,
    TextAreaField
)
from wtforms.fields.choices import RadioField
from wtforms.fields.form import FormField
from wtforms.form import Form
from flask_babel import lazy_gettext as _l

from changedetectionio.forms import processor_text_json_diff_form, StringDictKeyValue, valid_method, default_method


class RestockSettingsForm(Form):
    in_stock_processing = RadioField(label=_l('Re-stock detection'), choices=[
        ('in_stock_only', _l("In Stock only (Out Of Stock -> In Stock only)")),
        ('all_changes', _l("Any availability changes")),
        ('off', _l("Off, don't follow availability/restock")),
    ], default="in_stock_only")

    price_change_min = FloatField(_l('Below price to trigger notification'), [validators.Optional()],
                                  render_kw={"placeholder": _l("No limit"), "size": "10"})
    price_change_max = FloatField(_l('Above price to trigger notification'), [validators.Optional()],
                                  render_kw={"placeholder": _l("No limit"), "size": "10"})
    price_change_threshold_percent = FloatField(_l('Threshold in %% for price changes since the original price'), validators=[

        validators.Optional(),
        validators.NumberRange(min=0, max=100, message=_l("Should be between 0 and 100")),
    ], render_kw={"placeholder": "0%", "size": "5"})

    follow_price_changes = BooleanField(_l('Follow price changes'), default=True)


class RequestSettingsForm(Form):
    """Base form for request-specific settings"""
    headers = StringDictKeyValue('Request headers')
    body = TextAreaField(_l('Request body'), [validators.Optional()])
    method = SelectField(_l('Request method'), choices=valid_method, default=default_method)
    ignore_status_codes = BooleanField(_l('Ignore status codes (process non-2xx status codes as normal)'), default=False)
    proxy = RadioField(_l('Proxy'))


class request_settings_form(processor_text_json_diff_form):
    request_settings = FormField(RequestSettingsForm)

    def extra_tab_content(self):
        return _l('Request Settings')

    def extra_form_content(self):
        output = ""

        if getattr(self, 'watch', None) and getattr(self, 'datastore'):
            for tag_uuid in self.watch.get('tags'):
                tag = self.datastore.data['settings']['application']['tags'].get(tag_uuid, {})
                if tag.get('request_overrides_watch'):
                    # @todo - Quick and dirty, cant access 'url_for' here because its out of scope somehow
                    output = f"""<p><strong>Note! A Group tag overrides the request settings here.</strong></p><style>#request-fieldset-group {{ opacity: 0.6; }}</style>"""

        output += """
        {% from '_helpers.html' import render_field, render_checkbox_field, render_button %}
        <script>        
            $(document).ready(function () {
                toggleOpacity('#request_overrides_watch', '#request-fieldset-group', true);
            });
        </script>

        <fieldset id="request-fieldset-group">
            <div class="pure-control-group">
                <fieldset class="pure-group">
                    {{ render_field(form.request_settings.headers, rows=7, placeholder="Example
Cookie: foobar
User-Agent: wonderbra 1.0") }}
                    <div class="pure-form-message">Variables are supported in the request header values</div>
                </fieldset>
                <fieldset class="pure-group">
                    {{ render_field(form.request_settings.method) }}
                </fieldset>
                <fieldset class="pure-group">
                    {{ render_field(form.request_settings.body, rows=7, placeholder="Example
{
   \\"name\\":\\"John\\",
   \\"age\\":30,
   \\"car\\":null
}") }}
                    <div class="pure-form-message">Variables are supported in the request body</div>
                </fieldset>
                <fieldset class="pure-group">
                    {{ render_checkbox_field(form.request_settings.ignore_status_codes) }}
                </fieldset>
                {% if form.request_settings.proxy %}
                <fieldset class="pure-group inline-radio">
                    {{ render_field(form.request_settings.proxy, class="fetch-backend-proxy") }}
                    <span class="pure-form-message-inline">Choose a proxy for this request</span>
                </fieldset>
                {% endif %}
            </div>
        </fieldset>
        """
        return output


class processor_settings_form(processor_text_json_diff_form):
    restock_settings = FormField(RestockSettingsForm)

    def extra_tab_content(self):
        return _l('Restock & Price Detection')

    def extra_form_content(self):
        output = ""

        if getattr(self, 'watch', None) and getattr(self, 'datastore'):
            for tag_uuid in self.watch.get('tags'):
                tag = self.datastore.data['settings']['application']['tags'].get(tag_uuid, {})
                if tag.get('overrides_watch'):
                    # @todo - Quick and dirty, cant access 'url_for' here because its out of scope somehow
                    output = f"""<p><strong>Note! A Group tag overrides the restock and price detection here.</strong></p><style>#restock-fieldset-price-group {{ opacity: 0.6; }}</style>"""

        output += """
        {% from '_helpers.html' import render_field, render_checkbox_field, render_button %}
        <script>        
            $(document).ready(function () {
                toggleOpacity('#restock_settings-follow_price_changes', '.price-change-minmax', true);
            });
        </script>

        <fieldset id="restock-fieldset-price-group">
            <div class="pure-control-group">
                <fieldset class="pure-group inline-radio">
                    {{ render_field(form.restock_settings.in_stock_processing) }}
                </fieldset>
                <fieldset class="pure-group">
                    {{ render_checkbox_field(form.restock_settings.follow_price_changes) }}
                    <span class="pure-form-message-inline">Changes in price should trigger a notification</span>
                </fieldset>
                <fieldset class="pure-group price-change-minmax">               
                    {{ render_field(form.restock_settings.price_change_min, placeholder=watch.get('restock', {}).get('price')) }}
                    <span class="pure-form-message-inline">Minimum amount, Trigger a change/notification when the price drops <i>below</i> this value.</span>
                </fieldset>
                <fieldset class="pure-group price-change-minmax">
                    {{ render_field(form.restock_settings.price_change_max, placeholder=watch.get('restock', {}).get('price')) }}
                    <span class="pure-form-message-inline">Maximum amount, Trigger a change/notification when the price rises <i>above</i> this value.</span>
                </fieldset>
                <fieldset class="pure-group price-change-minmax">
                    {{ render_field(form.restock_settings.price_change_threshold_percent) }}
                    <span class="pure-form-message-inline">Price must change more than this % to trigger a change since the first check.</span><br>
                    <span class="pure-form-message-inline">For example, If the product is $1,000 USD originally, <strong>2%</strong> would mean it has to change more than $20 since the first check.</span><br>
                </fieldset>                
            </div>
        </fieldset>
        """
        return output