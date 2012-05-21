# -*- coding: utf-8 -*-
'''
Created on 15.04.2012

@author: moschlar
'''

import os
import logging

from tg import expose, tmpl_context as c, request, flash, app_globals as g, lurl
from tg.decorators import with_trailing_slash, before_validate, cached_property
from tgext.crud import CrudRestController, EasyCrudRestController

from tw.forms import TextField, BooleanRadioButtonList, SingleSelectField, Label, TextArea
from tw.forms.validators import FieldsMatch, Schema
from tw.tinymce import TinyMCE, mce_options_default
from formencode.validators import PlainText
from sqlalchemy import desc as _desc
import sqlalchemy.types
from tablesorter.widgets import JSSortableTableBase
from webhelpers.html.tags import link_to
from webhelpers.html.tools import mail_to

from sauce.model import (DBSession, Event, Lesson, Team, Student, Sheet,
                         Assignment, Test, Teacher, NewsItem)

__all__ = ['TeamsCrudController', 'StudentsCrudController', 'TeachersCrudController',
           'EventsCrudController', 'LessonsCrudController', 'SheetsCrudController',
           'AssignmentsCrudController', 'TestsCrudController', 'NewsItemController']

log = logging.getLogger(__name__)

#--------------------------------------------------------------------------------

passwordValidator = Schema(chained_validators=(FieldsMatch('password',
                                                           '_password',
                                                            messages={'invalidNoMatch':
                                                                 "Passwords do not match"}),))

def set_password(user):
    '''Sets the password for user to a new autogenerated password and displays it via flash'''
    password = user.generate_password()
    flash('Password for User %s set to: %s' % (user.user_name, password), 'info')
    return password

#--------------------------------------------------------------------------------

class FilteredCrudRestController(EasyCrudRestController):
    '''Generic base class for CrudRestControllers with filters'''
    
    def __init__(self, query_modifier=None, filters=[], filter_bys={},
                 menu_items={}, inject={}, btn_new=True, path_prefix='..'):
        '''Initialize FilteredCrudRestController with given options
        
        Arguments:
        
        ``query_modifier``:
            A callable that may modify the base query from the model entity
            if you need to use more sophisticated query functions than
            filters
        ``filters``:
            A list of sqlalchemy filter expressions
        ``filter_bys``:
            A dict of sqlalchemy filter_by keywords
        ``menu_items``:
            A dict of menu_items for ``EasyCrudRestController``
        ``inject``:
            A dict of values to inject into POST requests before validation
        ``btn_new``:
            Whether the "New <Entity>" link shall be displayed on get_all
        ``path_prefix``:
            Url prefix for linked paths (``menu_items`` and inter-entity links)
            Default: ``..``
        '''
        
        if not hasattr(self, 'table'):
            class Table(JSSortableTableBase):
                __entity__ = self.model
            self.table = Table(DBSession)
        
        self.btn_new = btn_new
        self.inject = inject
        
        # Since DBSession is a scopedsession we don't need to pass it around,
        # so we just use the imported DBSession here
        super(FilteredCrudRestController, self).__init__(DBSession, menu_items)
        
        self.table_filler.path_prefix = path_prefix.rstrip('/')
        
        def custom_do_get_provider_count_and_objs(**kw):
            '''Custom getter function respecting provided filters and filter_bys
            
            Returns the result count from the database and a query object
            
            Mostly stolen from sprox.sa.provider and modified accordingly
            '''
            
            # Get keywords that are not filters
            limit = kw.pop('limit', None)
            offset = kw.pop('offset', None)
            order_by = kw.pop('order_by', None)
            desc = kw.pop('desc', False)
            
            qry = self.model.query
            
            if query_modifier:
                qry = query_modifier(qry)
            
            # Process pre-defined filters
            if filters:
                qry = qry.filter(*filters)
            if filter_bys:
                qry = qry.filter_by(**filter_bys)
            
            # Process filters from url
            kwfilters = kw
            exc = False
            try:
                kwfilters = self.table_filler.__provider__._modify_params_for_dates(self.model, kwfilters)
            except ValueError as e:
                log.info('Could not parse date filters', exc_info=True)
                flash('Could not parse date filters: %s.' % e.message, 'error')
                exc = True
            
            try:
                kwfilters = self.table_filler.__provider__._modify_params_for_relationships(self.model, kwfilters)
            except (ValueError, AttributeError) as e:
                log.info('Could not parse relationship filters', exc_info=True)
                flash('Could not parse relationship filters: %s. '
                      'You can only filter by the IDs of relationships, not by their names.' % e.message, 'error')
                exc = True
            if exc:
                # Since any non-parsed kwfilter is bad, we just have to ignore them all now
                kwfilters = {}
            
            for field_name, value in kwfilters.iteritems():
                try:
                    field = getattr(self.model, field_name)
                    if self.table_filler.__provider__.is_relation(self.model, field_name) and isinstance(value, list):
                        value = value[0]
                        qry = qry.filter(field.contains(value))
                    else:
                        typ = self.table_filler.__provider__.get_field(self.model, field_name).type
                        if isinstance(typ, sqlalchemy.types.Integer):
                            value = int(value)
                            qry = qry.filter(field==value)
                        elif isinstance(typ, sqlalchemy.types.Numeric):
                            value = float(value)
                            qry = qry.filter(field==value)
                        else:
                            qry = qry.filter(field.like('%%%s%%' % value))
                except:
                    log.warn('Could not create filter on query', exc_info=True)
            
            # Get total count
            count = qry.count()
            
            # Process ordering
            if order_by is not None:
                field = getattr(self.model, order_by)
                if desc:
                    field = _desc(field)
                qry = qry.order_by(field)
            
            # Process pager options
            if offset is not None:
                qry = qry.offset(offset)
            if limit is not None:
                qry = qry.limit(limit)
            
            return count, qry
        # Assign custom getter function to table_filler
        self.table_filler._do_get_provider_count_and_objs = custom_do_get_provider_count_and_objs
        
        #TODO: We need a custom get_obj function, too to respect the filters...
        #      Probably a custom SAProvider would suffice.
    
    @with_trailing_slash
    @expose('mako:sauce.templates.get_all')
    @expose('json')
    #@paginate('value_list', items_per_page=7)
    def get_all(self, *args, **kw):
        """Return all records.
        Returns an HTML page with the records if not json.
        
        Stolen from tgext.crud.controller to disable pagination
        """
        c.paginators = None
        c.btn_new = self.btn_new
        
        d = super(FilteredCrudRestController, self).get_all(*args, **kw)
        
        if hasattr(self.table, '__search_fields__'):
            d['headers'] = []
            for field in self.table.__search_fields__:
                if isinstance(field, tuple):
                    d['headers'].append((field[0], field[1]))
                else:
                    d['headers'].append((field, field))
        
        return d

    @cached_property
    def mount_point(self):
        return '.'

    @classmethod
    def injector(cls, remainder, params):
        '''Injects the objects from self.inject into params
        
        self.inject has to be a dictionary of key, object pairs
        '''
        # Get currently dispatched controller instance
        #s = dispatched_controller() # Does not work, only returns last statically dispatch controller, but we use _lookup in EventsController
        s = request.controller_state.controller
        
        if hasattr(s, 'inject'):
            for i in s.inject:
                params[i] = s.inject[i]

# Register injection hook for POST requests
before_validate(FilteredCrudRestController.injector)(FilteredCrudRestController.post)

#--------------------------------------------------------------------------------

class TeamsCrudController(FilteredCrudRestController):
    
    model = Team
    
    __table_options__ = {
        #'__omit_fields__': ['lesson_id'],
        '__field_order__': ['id', 'name', 'lesson_id', 'lesson', 'students'],
        '__search_fields__': ['id', 'lesson_id', 'name'],
        'lesson': lambda filler, obj: link_to(obj.lesson.name, '../lessons/%d/edit' % obj.lesson.id),
        'students': lambda filler, obj: ', '.join(link_to(student.display_name, '../students/%d/edit' % student.id) for student in obj.students),
        }
    __form_options__ = {
        '__field_order__': ['id', 'name', 'lesson', 'students'],
        '__field_widget_types__': {'name': TextField,},
        '__field_widget_args__': {'students': {'size': 10},},
        }
    
    
class StudentsCrudController(FilteredCrudRestController):
    
    model = Student
    
    __table_options__ = {
        '__omit_fields__': ['password', '_password', 'submissions', 'type', 'groups',
                            'last_name', 'first_name'],
        '__field_order__': ['id', 'user_name', 'display_name', 'email_address',
                            'teams', '_lessons','created', 'new_password'],
        '__search_fields__': ['id', 'user_name', 'email_address', ('teams', 'team_id'), ('lessons', 'lesson_id')],
        '__headers__': {'new_password': u'Password',
                        '_lessons': u'Lessons'},
        'created': lambda filler, obj: obj.created.strftime('%x %X'),
        'display_name': lambda filler, obj: obj.display_name,
        'new_password': lambda filler, user: link_to(u'Generate new password',
                                                     '%d/password' % (user.id),
                                                     onclick='return confirm("Are you sure?")'),
        'email_address': lambda filler, obj: mail_to(obj.email_address, subject=u'[SAUCE]'),
        'teams': lambda filler, obj: ', '.join(link_to(team.name, '../teams/%d/edit' % team.id) for team in obj.teams),
        '_lessons': lambda filler, obj: ', '.join(link_to(lesson.name, '../lessons/%d/edit' % lesson.id) for lesson in obj._lessons),
        '__tablesorter_args__': {'headers': { 8: { 'sorter': False} }},
                            }
    __form_options__ = {
        '__omit_fields__': ['submissions', 'type', 'created', 'groups', 'display_name',
                            'password', '_password',
                            ],
        '__field_order__': ['id', 'user_name', 'last_name', 'first_name', 'email_address',
                            'teams', '_lessons',
                            ],
        '__field_widget_types__': {
                                   'user_name': TextField, 'email_address': TextField,
                                   'last_name': TextField, 'first_name': TextField,
                                  },
        '__field_widget_args__': {
                                  'user_name': {'help_text': u'Desired user name for login'},
                                  'teams': {'help_text': u'These are the teams this student belongs to',
                                            'size': 10},
                                  '_lessons': {'help_text': u'These are the lessons this students directly belongs to '
                                               '(If he belongs to a team that is already in a lesson, this can be left empty)',
                                            'size': 5},
                                  },
        '__base_validator__': passwordValidator,
        }
    __setters__ = {
                   'password': ('password', set_password),
                   }
    

class TeachersCrudController(FilteredCrudRestController):
    
    model = Teacher
    
    __table_options__ = {
        '__omit_fields__': ['password', '_password', 'type', 'groups', 'submissions',
                            'judgements', 'assignments', 'tests', 'sheets', 'news', 'events',
                            'last_name', 'first_name'],
        '__field_order__': ['id', 'user_name', 'display_name', 'email_address',
                            'lessons', 'created', 'new_password'],
        '__search_fields__': ['id', 'user_name', 'email_address', ('lessons', 'lesson_id')],
        '__headers__': {'new_password': u'Password'},
        'created': lambda filler, obj: obj.created.strftime('%x %X'),
        'display_name': lambda filler, obj: obj.display_name,
        'new_password': lambda filler, user: link_to(u'Generate new password',
                                                     '%d/password' % (user.id),
                                                     onclick='return confirm("Are you sure?")'),
        'email_address': lambda filler, obj: mail_to(obj.email_address, subject=u'[SAUCE]'),
        'lessons': lambda filler, obj: ', '.join(link_to(lesson.name, '../lessons/%d/edit' % lesson.id) for lesson in obj.lessons),
        '__tablesorter_args__': {'headers': { 7: { 'sorter': False} }},
                        }
    __form_options__ = {
        '__omit_fields__': ['submissions', 'type', 'created', 'groups', 'display_name',
                            'judgements', 'assignments', 'tests', 'sheets', 'news', 'events',
                            'password', '_password',
                            ],
        '__field_order__': ['id', 'user_name', 'last_name', 'first_name', 'email_address',
                            'lessons', 'groups'],
        '__field_widget_types__': {
                                   'user_name': TextField, 'email_address': TextField,
                                   'last_name': TextField, 'first_name': TextField,
                                  },
        '__field_widget_args__': {
                                  'user_name': {'help_text': u'Desired user name for login'},
                                  'lessons': {'help_text': u'These are the lessons this teacher teaches',
                                              'size': 10},
                                  },
        '__base_validator__': passwordValidator,
        }
    __setters__ = {
                   'password': ('password', set_password),
                   }

#--------------------------------------------------------------------------------

class EventsCrudController(FilteredCrudRestController):
    
    model = Event
    
    __table_options__ = {
        '__omit_fields__': ['id', 'description', 'teacher_id', 'password',
                            'assignments', 'lessons', 'sheets', 'news',
                           ],
        '__field_order__': ['type', '_url', 'name', 'public',
                            'start_time', 'end_time', 'teacher', 'teachers'],
        '__search_fields__': ['id', '_url', 'name', 'teacher_id'],
        '__headers__': {'_url': 'Url'},
        'start_time': lambda filler, obj: obj.start_time.strftime('%x %X'),
        'end_time': lambda filler, obj: obj.end_time.strftime('%x %X'),
        'teacher': lambda filler, obj: link_to(obj.teacher.display_name, '../teachers/%d/edit' % obj.teacher.id),
        'teachers': lambda filler, obj: ', '.join(link_to(teacher.display_name, '../teachers/%d/edit' % teacher.id) for teacher in obj.teachers),
        }
    __form_options__ = {
        '__hide_fields__': ['teacher'],
        '__omit_fields__': ['assignments', 'sheets', 'news', 'lessons'],
        '__field_order__': ['type', '_url', 'name', 'description',
                            'public', 'start_time', 'end_time', 'password'],
        '__field_widget_types__': {'name':TextField, 'description':TinyMCE,
                                   'public': BooleanRadioButtonList, '_url':TextField,
                                   'type': SingleSelectField, 'password':TextField,
                                  },
        '__field_validator_types__': {'_url': PlainText, },
        '__field_widget_args__': {
                                  'type': dict(options=[('course','Course'), ('contest','Contest')]),
                                  'description': {'mce_options': mce_options_default},
                                  '_url': {'help_text': u'Will be part of the url, has to be unique and url-safe'},
                                  'public': {'help_text': u'Make event visible for students', 'default': True},
                                  'password': {'help_text': u'Password for student self-registration. Currently not implemented'},
                                 },
        '__require_fields__': ['_url'],
        }

class LessonsCrudController(FilteredCrudRestController):
    
    model = Lesson
    
    __table_options__ = {
        '__omit_fields__': ['id', 'event_id', 'event', '_url'],
        '__field_order__': ['lesson_id', 'name', 'teacher_id',
                            'teacher', 'teams', '_students'],
        '__search_fields__': ['id', 'lesson_id', 'name', 'teacher_id', ('teams','team_id'), ('_students','student_id')],
        '__headers__': {'_students': 'Students'},
        'teacher': lambda filler, obj: link_to(obj.teacher.display_name, '%s/teachers/%d/edit' % (filler.path_prefix, obj.teacher.id)),
        'teams': lambda filler, obj: ', '.join(link_to(team.name, '%s/teams/%d/edit' % (filler.path_prefix, team.id)) for team in obj.teams),
        '_students': lambda filler, obj: ', '.join(link_to(student.display_name, '%s/students/%d/edit' % (filler.path_prefix, student.id)) for student in obj._students),
        }
    __form_options__ = {
        '__omit_fields__': ['_url', 'teams', '_students'],
        '__hide_fields__': ['event'], # If the field is omitted, it does not get validated!
        '__field_order__': ['id', 'lesson_id', 'name', 'teacher'],
        '__field_widget_types__': {'name': TextField},
        '__field_widget_args__': {
                                  'lesson_id': {'help_text': u'This id will be part of the url and has to be unique for the parent event'},
                                  'teams': {'size': 10},
                                 },
        '__require_fields__': [
                               #'event',
                               ],
        }
    

class SheetsCrudController(FilteredCrudRestController):
    
    model = Sheet
    
    __table_options__ = {
        '__omit_fields__': ['id', 'description', 'event_id', 'event', 'teacher',
                            'teacher_id', '_url', '_start_time', '_end_time'],
        '__field_order__': ['sheet_id', 'name', 'public',
                            'start_time', 'end_time', 'assignments'],
        '__search_fields__': ['id', 'sheet_id', 'name', ('assignments', 'assignment_id')],
        'start_time': lambda filler, obj: obj.start_time.strftime('%x %X'),
        'end_time': lambda filler, obj: obj.end_time.strftime('%x %X'),
        'assignments': lambda filler, obj: ', '.join(link_to(ass.name, '../assignments/%d/edit' % ass.id) for ass in obj.assignments),
        }
    __form_options__ = {
        '__omit_fields__': ['_url', 'assignments'],
        '__hide_fields__': ['teacher', 'event'],
        '__field_order__': ['id', 'sheet_id', 'name', 'description',
                            'public', '_start_time', '_end_time'],
        '__field_widget_types__': {
                                   'name': TextField, 'description': TinyMCE,
                                   'public': BooleanRadioButtonList,
                                  },
        '__field_widget_args__': {
                                  '_start_time':{'default': u'', 'help_text': u'Leave empty to use value from event'},
                                  '_end_time':{'default': u'', 'help_text': u'Leave empty to use value from event'},
                                  'description':{'mce_options': mce_options_default},
                                  'sheet_id': {'help_text': u'This id will be part of the url and has to be unique for the parent event'},
                                  'public': {'help_text': u'Make sheet visible for students', 'default': True},
                                  #'assignments': {'size': 10},
                                 },
        '__require_fields__': ['sheet_id'],
        }

class AssignmentsCrudController(FilteredCrudRestController):
    
    model = Assignment
    
    __table_options__ = {
        '__omit_fields__': ['id', 'event_id', '_event', '_url',
                            'teacher_id', 'teacher', 'allowed_languages',
                            '_teacher', 'description', 'tests',
                            'submissions', 'show_compiler_msg',
                            '_start_time', '_end_time'],
        '__field_order__': ['sheet_id', 'sheet', 'assignment_id', 'name',
                            'public', 'start_time', 'end_time',
                            'timeout'],
        '__search_fields__': ['id', 'sheet_id', 'assignment_id', 'name'],
        'start_time': lambda filler, obj: obj.start_time.strftime('%x %X'),
        'end_time': lambda filler, obj: obj.end_time.strftime('%x %X'),
        'sheet': lambda filler, obj: link_to(obj.sheet.name, '../sheets/%d/edit' % obj.sheet.id),
        }
    __form_options__ = {
        '__omit_fields__': ['tests', 'submissions', '_event', '_teacher', '_url'],
        '__field_order__': ['id', 'sheet', 'assignment_id', 'name', 'description',
                            'public', '_start_time', '_end_time',
                            'timeout', 'allowed_languages', 'show_compiler_msg'],
        '__field_widget_types__': {
                                   'name': TextField, 'description': TinyMCE,
                                   'show_compiler_msg': BooleanRadioButtonList,
                                   'public': BooleanRadioButtonList,
                                  },
        '__field_widget_args__': {
                                  'assignment_id': {'help_text': u'Will be part of the url and has to be unique for the parent sheet'},
                                  'description': {'mce_options': mce_options_default},
                                  '_start_time': {'default': u'', 'help_text': u'Leave empty to use value from sheet'},
                                  '_end_time': {'default': u'', 'help_text': u'Leave empty to use value from sheet'},
                                  'timeout': {'help_text': u'Default timeout value for test cases, leave empty for no time limit'},
                                  'allowed_languages': {'size': 6},
                                  'show_compiler_msg': {'help_text': u'Show error messages or warnings from the compiler run', 'default': True},
                                  'public': {'help_text': u'Make assignment visible for students', 'default': True},
                                 },
        '__require_fields__': ['assignment_id',
                               #'sheet', # Breaks sprox' pre-selection...
                               ],
        }

#--------------------------------------------------------------------------------

class TestsCrudController(FilteredCrudRestController):
    
    model = Test
    
    __table_options__ = {
        '__omit_fields__': ['id', 'input_data', 'output_data', 'input_filename', 'output_filename',
                            'ignore_case', 'ignore_returncode', 'show_partial_match',
                            'splitlines', 'split', 'comment_prefix', 'separator',
                            'parse_int', 'parse_float', 'float_precision', 'sort',
                            'teacher_id', 'teacher', 'testruns'],
        '__field_order__': ['id', 'assignment_id', 'assignment', 'visible', '_timeout', 'argv',
                            'input_type', 'output_type'],
        '__search_fields__': ['id', 'assignment_id'],
        '__headers__': {'_timeout': 'Timeout'},
        'assignment': lambda filler, obj: link_to(obj.assignment.name, '../assignments/%d/edit' % obj.assignment.id),
        }
    __form_options__ = {
        '__omit_fields__': ['testruns'],
        '__hide_fields__': ['teacher'],
        '__add_fields__': {
                           'docs': Label('docs', text='Please read the <a href="%s">' % lurl('/docs/tests') +
                                              'Test configuration documentation</a>!'),
                           'ignore_opts': Label('ignore_opts', text='Output ignore options'),
                           'split_opts': Label('split_opts', text='Output splitting options'),
                           'parse_opts': Label('parse_opts', text='Output parsing options'),
                           },
        '__field_order__': ['docs', 'id', 'assignment', 'visible',
                            'input_data', 'output_data',
                            'input_type', 'output_type',
                            'input_filename', 'output_filename',
                            '_timeout', 'argv',
                            'ignore_opts',
                            'ignore_case', 'comment_prefix', 'ignore_returncode', 'show_partial_match',
                            'split_opts',
                            'splitlines', 'split', 'separator', 'sort',
                            'parse_opts',
                            'parse_int', 'parse_float', 'float_precision'],
        '__field_widget_types__': {
                                   'argv': TextField,
                                   'visible': BooleanRadioButtonList,
                                   'input_filename': TextField, 'output_filename': TextField,
                                   'input_type': SingleSelectField, 'output_type': SingleSelectField,
#                                   'input_data': FileField, 'output_data': FileField,
                                   'input_data': TextArea, 'output_data': TextArea,
                                   #'separator':         BooleanRadioButtonList,
                                   'ignore_case':        BooleanRadioButtonList,
                                   'ignore_returncode':  BooleanRadioButtonList,
                                   'show_partial_match': BooleanRadioButtonList,
                                   'splitlines':         BooleanRadioButtonList,
                                   'split':              BooleanRadioButtonList,
                                   'parse_int':          BooleanRadioButtonList,
                                   'parse_float':        BooleanRadioButtonList,
                                   'sort':               BooleanRadioButtonList,
                                  },
        '__field_widget_args__': {
                                  'argv': {'help_text': u'''
Command line arguments

Possible variables are:
    {path}: Absolute path to temporary working directory
    {infile}: Full path to test input file
    {outfile}: Full path to test output file
                                  '''},
                                  'visible': {'help_text': u'Whether test is shown to users or not', 'default': True},
                                  '_timeout': {'help_text': u'Timeout value, leave empty to use value from assignment'},
                                  'input_type': dict(options=[('stdin','stdin'), ('file','file')]),
                                  'output_type': dict(options=[('stdout','stdout'), ('file','file')]),
#                                  'input_data': dict(help_text=u'Warning, this field always overwrites database entries'),
#                                  'output_data': dict(help_text=u'Warning, this field always overwrites database entries'),
                                  'separator': {'help_text': u'The separator string used for splitting and joining, default is None (whitespace)'},
                                  'ignore_case': {'help_text': u'Call .lower() on output before comparison', 'default': True},
                                  'ignore_returncode': {'help_text': u'Ignore test process returncode', 'default': True},
                                  'comment_prefix': {'help_text': u'Ignore all lines that start with comment_prefix',},
                                  'show_partial_match': {'help_text': u'Recognize partial match and show to user', 'default': True},
                                  'splitlines': {'help_text': u'Call .splitlines() on full output before comparison', 'default': False},
                                  'split': {'help_text': u'Call .split() on full output of output before comparison or on each line from .splitlines() if splitlines is set'},
                                  'parse_int': {'help_text': u'Parse every substring in output to int before comparison', 'default': False},
                                  'parse_float': {'help_text': u'Parse every substring in output to float before comparison', 'default': False},
                                  'float_precision': {'help_text': u'''The precision (number of decimal digits) to compare for floats'''},
                                  'sort': {'help_text': u'''Sort output and test data before comparison
Parsing is performed first, if enabled
Results depends on whether splitlines and/or split are set:
if split and splitlines:
    2-dimensional array in which only the second dimension 
    is sorted (e.g. [[3, 4], [1, 2]])
if only split or only splitlines:
    1-dimensional list is sorted by the types default comparator
    ''', 'default': False},
                                 },
#        '__field_validator_types__': {
#                                      'input_data': FieldStorageUploadConverter,
#                                      'output_data': FieldStorageUploadConverter,
#                                     },
        '__require_fields__': [
                               #'assignment',
                               ],
        }

#--------------------------------------------------------------------------------

class NewsItemController(FilteredCrudRestController):
    
    model = NewsItem
    
    __table_options__ = {
        '__omit_fields__': ['event_id', 'teacher_id', 'teacher'],
        '__field_order__': ['id', 'date', 'subject', 'message', 'public'],
        'date': lambda filler, obj: obj.date.strftime('%x %X'),
        }
    __form_options__ = {
        '__hide_fields__': ['teacher'],
        '__field_order__': ['id', 'date', 'event', 'subject', 'message', 'public'],
        '__field_widget_types__': {'subject': TextField, 'public': BooleanRadioButtonList,},
        '__field_widget_args__': {'date': {'default': ''},
                                  'event': {'help_text': u'If an event is set, the NewsItem will be shown on the event page; '
                                            'if no event is set, the NewsItem is shown on the news page'},
                                  },
        }
