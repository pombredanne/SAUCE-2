'''
Created on 14.04.2012

@author: moschlar
'''

import logging

from tg import request, flash

from tgext.crud.utils import SortableTableBase
from sprox.formbase import AddRecordForm, EditableForm, Field
from sprox.tablebase import TableBase
from sprox.fillerbase import TableFiller
#from sprox.dojo.formbase import DojoAddRecordForm # renders TableForm to ugly at the moment, Issue #9
from tw.forms import TextField, SingleSelectField, BooleanRadioButtonList, CalendarDateTimePicker, FileField
from tw.forms.validators import String, DateTimeConverter, Int, Number, FileUploadKeeper, FieldStorageUploadConverter
from tw.tinymce import TinyMCE

from sauce.model import DBSession, Event, Lesson, Sheet, Assignment, Test, Submission, Student, Team, User
from sauce.lib.helpers import cut, link
from sqlalchemy.sql.expression import desc as _desc

log = logging.getLogger(__name__)

#----------------------------------------------------------------------

class EventForm(object):
    '''Mixin for event form widgets'''
    __model__ = Event
    #__omit_fields__ = ['news', 'lessons', 'sheets', 'assignments']
    __limit_fields__ = __field_order__ = ['name', '_url', 'type', 'description', 'start_time', 'end_time', 'public', 'password', 'teacher', 'teachers']
    __require_fields__ = ['name', '_url']
    
    name = TextField
    _url = Field(TextField, String(min=1))
    type = SingleSelectField('type', options=[('course', 'Course'), ('contest', 'Contest')])
    description = TinyMCE
    start_time = Field(CalendarDateTimePicker, DateTimeConverter)
    end_time = Field(CalendarDateTimePicker, DateTimeConverter)
    password = TextField
    public = BooleanRadioButtonList

class NewEventForm(EventForm, AddRecordForm):
    '''Form widget for creating a new event'''
new_event_form = NewEventForm(DBSession)

class EditEventForm(EventForm, EditableForm):
    ''''Form widget for editing an event'''
edit_event_form = EditEventForm(DBSession)

#----------------------------------------------------------------------

class LessonTable(TableBase):
    __model__ = Lesson
    __omit_fields__ = ['__actions__']
    __limit_fields__ = __field_order__ = ['lesson_id', 'name', 'teacher', 'teams']
    __xml_fields__ = ['name']

lesson_table = LessonTable(DBSession)

class LessonTableFiller(TableFiller):
    __model__ = Lesson
    
    def name(self, obj):
        return u'<a href="%s/lessons/%d">%s</a>' % (obj.event.url, obj.id, obj.name)

lesson_filler = LessonTableFiller(DBSession)

#----------------------------------------------------------------------

class SheetForm(object):
    '''Mixin for sheet form widgets'''
    __model__ = Sheet
    #__omit_fields__ = ['news', 'lessons', 'sheets', 'assignments']
    __limit_fields__ = __field_order__ = ['name', 'sheet_id', 'description', '_start_time', '_end_time', 'public', 'teacher']
    __require_fields__ = ['name', 'sheet_id']
    
    name = TextField
    sheet_id = Field(TextField, Int)
    description = TinyMCE
    _start_time = Field(CalendarDateTimePicker, DateTimeConverter)
    _end_time = Field(CalendarDateTimePicker, DateTimeConverter)
    public = BooleanRadioButtonList
    
    __field_widget_args__ = dict(_start_time=dict(help_text=u'Leave empty to use value from event', default=u''), 
                           _end_time=dict(help_text=u'Leave empty to use value from event', default=u''))
    
class NewSheetForm(SheetForm, AddRecordForm):
    '''Form widget for creating a new sheet'''
new_sheet_form = NewSheetForm(DBSession)

class EditSheetForm(SheetForm, EditableForm):
    ''''Form widget for editing a sheet'''
edit_sheet_form = EditSheetForm(DBSession)

#----------------------------------------------------------------------

class AssignmentForm(object):
    '''Mixin for assignment form widgets'''
    __model__ = Assignment
    #__omit_fields__ = ['news', 'lessons', 'sheets', 'assignments']
    __limit_fields__ = __field_order__ = ['name', 'assignment_id', 'description', 
                                          '_start_time', '_end_time', 'timeout', 
                                          'allowed_languages', 'show_compiler_msg', 
                                          'public']
    __require_fields__ = ['name', 'assignment_id']
    
    name = TextField
    assignment_id = Field(TextField, Int)
    description = TinyMCE
    _start_time = Field(CalendarDateTimePicker, DateTimeConverter)
    _end_time = Field(CalendarDateTimePicker, DateTimeConverter)
    timeout = Number
    show_compiler_msg = BooleanRadioButtonList
    public = BooleanRadioButtonList
    
    __field_widget_args__ = dict(_start_time=dict(help_text=u'Leave empty to use value from sheet', default=u''), 
                           _end_time=dict(help_text=u'Leave empty to use value from sheet', default=u''))

class NewAssignmentForm(AssignmentForm, AddRecordForm):
    '''Form widget for creating a new assignment'''
new_assignment_form = NewAssignmentForm(DBSession)

class EditAssignmentForm(AssignmentForm, EditableForm):
    ''''Form widget for editing a assignment'''
edit_assignment_form = EditAssignmentForm(DBSession)

#----------------------------------------------------------------------

class TestTable(TableBase):
    __model__ = Test
    __limit_fields__ = __field_order__ = ['id', 'assignment', 'input_type', 'output_type',
                                          'input_filename', 'output_filename',
                                          'input_data', 'output_data',
                                          '_timeout', 'visible', 'teacher']
test_table = TestTable(DBSession)

class TestTableFiller(TableFiller):
    __model__ = Test
    
    input_data = lambda self, obj: cut(obj.input_data or u'', max=50)
    output_data = lambda self, obj: cut(obj.output_data or u'', max=50)
    
    def _do_get_provider_count_and_objs(self, assignment, **kw):
        tests = Test.query.filter_by(assignment_id=assignment.id).all()
        return len(tests), tests
    
test_table_filler = TestTableFiller(DBSession)

#----------------------------------------------------------------------

class TestForm(object):
    '''Mixin for test form widgets'''
    __model__ = Test
    #__omit_fields__ = ['news', 'lessons', 'sheets', 'assignments']
    __limit_fields__ = __field_order__ = ['visible', '_timeout','argv', 
                                          'input_type', 'output_type',  
                                          'input_filename', 'output_filename', 
                                          'input_data', 'output_data']
    __require_fields__ = ['assignment']
    __headers__ = dict(_timeout=u'Timeout')
    
    visible = BooleanRadioButtonList
    input_type = SingleSelectField('input_type', options=[('stdin','stdin'), ('file','file')])
    output_type = SingleSelectField('output_type', options=[('stdout','stdout'), ('file','file')])
    input_filename = TextField
    output_filename = TextField
    argv = TextField
    _timeout = Number
    input_data = Field(FileField, FieldStorageUploadConverter)
    output_data = Field(FileField, FieldStorageUploadConverter)
    
    __field_widget_args__ = dict(_timeout=dict(help_text=u'Leave empty to use value from sheet'))

class NewTestForm(TestForm, AddRecordForm):
    '''Form widget for creating a new test'''
new_test_form = NewTestForm(DBSession)

class EditTestForm(TestForm, EditableForm):
    ''''Form widget for editing a test'''
edit_test_form = EditTestForm(DBSession)

#----------------------------------------------------------------------

def _actions(filler, subm):
    result = link(u'Show', subm.url + '/show')
    if hasattr(request, 'teacher') and request.teacher:
        result += ' ' + link(u'Judge', subm.url + '/judge')
    return result


class SubmissionTable(SortableTableBase):
    __model__ = Submission
    __omit_fields__ = ['source', 'assignment_id', 'language_id', 'user_id',
                       'testruns', 'filename']
    __field_order__ = ['id', 'user', 'assignment', 'language', 'created', 'modified',
                       'complete', 'result', 'judgement', 'grade']
    __add_fields__ = {'result': None, 'judgement': None, 'grade': None}
    #__headers__ = {'assignment': '<a href="?order_by=assignment_id">Assignment</a>'}

class SubmissionTableFiller(TableFiller):
    __model__ = Submission
    __omit_fields__ = ['source', 'assignment_id', 'language_id', 'user_id',
                       'testruns', 'filename']
    __add_fields__ = {'result': None, 'judgement': None, 'grade': None}
    __actions__ = _actions
    
    def result(self, obj):
        if obj.complete:
            if obj.result:
                return u'<span class="green">Success</a>'
            else:
                return u'<span class="red">Failed</a>'
        else:
            return u'None'
    
    def judgement(self, obj):
        if obj.judgement:
            return u'<a href="%s/judge">Yes</a>' % (obj.url)
        else:
            return u'<a href="%s/judge">No</a>' % (obj.url)
    
    def grade(self, obj):
        if obj.judgement and obj.judgement.grade:
            return unicode(obj.judgement.grade)
        else:
            return u''
    
    #def id(self, obj):
    #    return u'<a style="text-decoration:underline;" href="%s/judge">Submission %d</a>' % (obj.url, obj.id)
    
    def __init__(self, lesson=None, *args, **kw):
        self.lesson = lesson
        super(SubmissionTableFiller, self).__init__(*args, **kw)

#----------------------------------------------------------------------

