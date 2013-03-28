# -*- coding: utf-8 -*-
'''
Created on 15.04.2012

@author: moschlar
'''
#
## SAUCE - System for AUtomated Code Evaluation
## Copyright (C) 2013 Moritz Schlarb
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU Affero General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU Affero General Public License for more details.
##
## You should have received a copy of the GNU Affero General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
import logging

import inspect
from itertools import groupby
from webhelpers.html.builder import literal

from tg import expose, tmpl_context as c, request, flash, lurl, abort
from tg.decorators import before_validate, before_call, before_render,\
    cached_property, override_template, with_trailing_slash
from tg.controllers.tgcontroller import TGController
from tgext.crud import CrudRestController, EasyCrudRestController
from tgext.crud.controller import CrudRestControllerHelpers

from sauce.model import DBSession

import tw2.bootstrap.forms as twb
import tw2.jqplugins.chosen.widgets as twjc
import sprox.widgets.tw2widgets.widgets as sw
from sauce.widgets.datagrid import JSSortableDataGrid

from sprox.sa.widgetselector import SAWidgetSelector
from sauce.controllers.crc.provider import FilterSAORMSelector
from sprox.fillerbase import TableFiller, AddFormFiller, EditFormFiller
from sprox.formbase import AddRecordForm, EditableForm

import transaction
from sqlalchemy.exc import IntegrityError, DatabaseError, ProgrammingError
errors = (IntegrityError, DatabaseError, ProgrammingError)


__all__ = ['FilterCrudRestController']

log = logging.getLogger(__name__)


#--------------------------------------------------------------------------------

class ChosenPropertyMultipleSelectField(twjc.ChosenMultipleSelectField, sw.PropertyMultipleSelectField):

    def _validate(self, value, state=None):
        # Fix inspired by twf.MultipleSelectionField
        if value and not isinstance(value, (list, tuple)):
            value = [value]
        return super(ChosenPropertyMultipleSelectField, self)._validate(value, state)


class ChosenPropertySingleSelectField(twjc.ChosenSingleSelectField, sw.PropertySingleSelectField):
    pass


class MyWidgetSelector(SAWidgetSelector):
    default_multiple_select_field_widget_type = ChosenPropertyMultipleSelectField
    default_single_select_field_widget_type = ChosenPropertySingleSelectField

    def __init__(self, *args, **kw):
        super(MyWidgetSelector, self).__init__(*args, **kw)
#        self.default_widgets.update({sqlat.DateTime: twb.CalendarDateTimePicker})

#--------------------------------------------------------------------------------

class CrudIndexController(TGController):

    def __init__(self, *args, **kw):
        super(CrudIndexController, self).__init__(*args, **kw)
        self.helpers = CrudRestControllerHelpers()

    def _before(self, *args, **kw):
        c.title = self.title
        c.menu_items = self.menu_items
        #c.kept_params = self._kept_params()
        c.crud_helpers = self.helpers
        #c.crud_style = self.style

    @with_trailing_slash
    @expose('sauce.templates.crc.index')
    def index(self):
        return dict(page='event')


#--------------------------------------------------------------------------------

class FilterCrudRestController(EasyCrudRestController):
    '''Generic base class for CrudRestControllers with filters'''

    def __init__(self, query_modifier=None, query_modifiers={},
                 menu_items={}, inject={},
                 allow_new=True, allow_edit=True, allow_delete=True,
                 **kw):
        '''Initialize FilteredCrudRestController with given options

        Arguments:

        ``query_modifier``:
            A callable that may modify the base query from the model entity
        ``query_modifiers``:
            A dict of callable that may modify the relationship query from the model entity
            the keys are the remote side classes
        ``menu_items``:
            A dict of menu_items for ``EasyCrudRestController``
        ``inject``:
            A dict of values to inject into POST requests before validation
        ``allow_new``:
            Whether the "New <Entity>" link shall be displayed on get_all
            and the url /<entity/new will be accesible
        ``allow_edit``:
            Whether the "Edit" link shall be displayed in the actions column
            on get_all and the url /<entity/<id>/delete will be accesible
        ``allow_delete``:
            Whether the "Delete" link shall be displayed in the actions column
            on get_all and the url /<entity/<id>/delete will be accesible
        '''

        self.inject = inject

        self.allow_new = allow_new
        self.allow_edit = allow_edit
        self.allow_delete = allow_delete

#        if not hasattr(self, 'table'):
#            class Table(JSSortableTableBase):
#                __entity__ = self.model
#            self.table = Table(DBSession)

        # To effectively disable pagination and fix issues with tgext.crud.util.SmartPaginationCollection
        if not hasattr(self, 'table_filler'):
            class MyTableFiller(TableFiller):
                __entity__ = self.model
                __actions__ = self.custom_actions
                __provider_type_selector_type__ = FilterSAORMSelector
            self.table_filler = MyTableFiller(DBSession,
                query_modifier=query_modifier, query_modifiers=query_modifiers)

        if self.allow_edit and not hasattr(self, 'edit_form'):
            class EditForm(EditableForm):
                __entity__ = self.model
                __provider_type_selector_type__ = FilterSAORMSelector
            self.edit_form = EditForm(DBSession,
                query_modifier=query_modifier, query_modifiers=query_modifiers)

        if self.allow_edit and not hasattr(self, 'edit_filler'):
            class EditFiller(EditFormFiller):
                __entity__ = self.model
                __provider_type_selector_type__ = FilterSAORMSelector
            self.edit_filler = EditFiller(DBSession,
                query_modifier=query_modifier, query_modifiers=query_modifiers)

        if self.allow_new and not hasattr(self, 'new_form'):
            class NewForm(AddRecordForm):
                __entity__ = self.model
                __provider_type_selector_type__ = FilterSAORMSelector
            self.new_form = NewForm(DBSession,
                query_modifier=query_modifier, query_modifiers=query_modifiers)

        if self.allow_new and not hasattr(self, 'new_filler'):
            class NewFiller(AddFormFiller):
                __entity__ = self.model
                __provider_type_selector_type__ = FilterSAORMSelector
            self.new_filler = NewFiller(DBSession,
                query_modifier=query_modifier, query_modifiers=query_modifiers)

        self.__table_options__['__base_widget_type__'] = JSSortableDataGrid
        if '__base_widget_args__' in self.__table_options__:
            if 'headers' in self.__table_options__['__base_widget_args__']:
                self.__table_options__['__base_widget_args__']['headers'].update({0: {'sorter': False}})
            else:
                self.__table_options__['__base_widget_args__'].update({'headers': {0: {'sorter': False}}})
        else:
            self.__table_options__['__base_widget_args__'] = {'headers': {0: {'sorter': False}}}

        self.__form_options__['__base_widget_type__'] = twb.HorizontalForm
        self.__form_options__['__widget_selector__'] = MyWidgetSelector()

        # Since DBSession is a scopedsession we don't need to pass it around,
        # so we just use the imported DBSession here
        super(FilterCrudRestController, self).__init__(DBSession, menu_items)

    def _adapt_menu_items(self, menu_items):
        '''Overwrite from CrudRestController to preserve ordering'''
        adapted_menu_items = type(menu_items)()

        for link, model in menu_items.iteritems():
            if inspect.isclass(model):
                adapted_menu_items[link + 's'] = model.__name__
            else:
                adapted_menu_items[link] = model
        return adapted_menu_items

    def custom_actions(self, obj):
        ''''Display bootstrap-styled action fields respecting the allow_* properties'''
        result = []
        count = 0
        try:
            result.append(u'<a href="' + obj.url + '" class="btn btn-mini" title="Show">'
                u'<i class="icon-eye-open"></i></a>')
            count += 1
        except:
            pass
        try:
            primary_fields = self.table_filler.__provider__.get_primary_fields(self.table_filler.__entity__)
            pklist = u'/'.join(map(lambda x: unicode(getattr(obj, x)), primary_fields))
            result.append(u'<a href="' + pklist + '/edit" class="btn btn-mini" title="Edit">'
                u'<i class="icon-pencil"></i></a>')
        except:
            pass
        if self.allow_delete:
            result.append(
                u'<a class="btn btn-mini btn-danger" href="./%d/delete" title="Delete">'
                u'  <i class="icon-remove icon-white"></i>'
                u'</a>' % (obj.id))
        return literal('<div class="btn-group" style="width: %dpx;">'
            % (len(result) * 30) + ''.join(result) + '</div>')

    def _before(self, *args, **kw):
        super(FilterCrudRestController, self)._before(*args, **kw)
        try:
            c.menu_item = self.menu_item
        except:
            c.menu_item = self.model.__name__

    @expose('sauce.templates.crc.get_delete')
    def get_delete(self, *args, **kw):
        '''This is the code that creates a confirm_delete page'''
        if not self.allow_delete:
            abort(403)
        pks = self.provider.get_primary_fields(self.model)
        kw, d = {}, {}
        for i, pk in  enumerate(pks):
            kw[pk] = args[i]
        for i, arg in enumerate(args):
            d[pks[i]] = arg

        obj = self.provider.delete(self.model, d)
        deps = u'<dl>'
        for k, g in groupby(sorted(o for o in DBSession.deleted if o != obj), lambda x: type(x)):
            deps += u'<dt>' + unicode(k.__name__) + u'</dt>'
            deps += u'<dd>' + u', '.join(sorted(unicode(o) for o in g)) + u'</dd>'
        deps += u'</dl>'

        transaction.doom()

        #obj = self.edit_filler.__provider__.get_obj(self.model, params=kw, fields=self.edit_filler.__fields__)
        pklist = u'/'.join(map(lambda x: unicode(getattr(obj, x)), pks))

        return dict(obj=obj,
            model=self.model.__name__,
            deps=deps,
            pk_count=len(pks), pklist=pklist)

    @staticmethod
    def before_get_all(remainder, params, output):
        # Disable pagination for get_all
        output['value_list'].page_count = 0
        #output['value_list'] = output['value_list'].original_collection
        output['value_list'] = output['value_list'].collection
        c.paginators = []

        # Use my bootstrap-enabled template
        override_template(FilterCrudRestController.get_all,
            'mako:sauce.templates.crc.get_all')

        # And respect __search_fields__ as long as tgext.crud doesn't use them
        s = request.controller_state.controller
        if hasattr(s.table, '__search_fields__'):
            output['headers'] = []
            for field in s.table.__search_fields__:
                if isinstance(field, tuple):
                    output['headers'].append((field[0], field[1]))
                else:
                    output['headers'].append((field, field))

        for allow in ('allow_new', 'allow_edit', 'allow_delete'):
            setattr(c, allow, getattr(s, allow, True))

    @staticmethod
    def before_new(remainder, params, output):
        s = request.controller_state.controller
        if not getattr(s, 'allow_new', True):
            abort(403)
        # Use my bootstrap-enabled template
        override_template(FilterCrudRestController.new,
            'mako:sauce.templates.crc.new')

    @staticmethod
    def before_edit(remainder, params, output):
        s = request.controller_state.controller
        if not getattr(s, 'allow_edit', True):
            abort(403)
        # Use my bootstrap-enabled template
        override_template(FilterCrudRestController.edit,
            'mako:sauce.templates.crc.edit')

    @cached_property
    def mount_point(self):
        return '.'

    @staticmethod
    def injector(remainder, params):
        '''Injects the objects from self.inject into params

        self.inject has to be a dictionary of key, object pairs
        '''
        # Get currently dispatched controller instance
        # Does not work, only returns last statically dispatch controller,
        # but we use _lookup in EventsController
        #s = dispatched_controller()
        s = request.controller_state.controller

        for i in getattr(s, 'inject', []):
            params[i] = s.inject[i]


# Register injection hook for POST requests
before_validate(FilterCrudRestController.injector)(FilterCrudRestController.post)

# Register hook for get_all
before_render(FilterCrudRestController.before_get_all)(FilterCrudRestController.get_all)
# Register hook for new
before_render(FilterCrudRestController.before_new)(FilterCrudRestController.new)
# Register hook for edit
before_render(FilterCrudRestController.before_edit)(FilterCrudRestController.edit)
