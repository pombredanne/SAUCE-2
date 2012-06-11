# -*- coding: utf-8 -*-
"""EventAdmin controller module

@author: moschlar
"""

import logging

# turbogears imports
from tg import expose, abort, request, tmpl_context as c, TGController
from tg.decorators import without_trailing_slash

# third party imports
#from tg.i18n import ugettext as _
from repoze.what.predicates import Any, has_permission

# project specific imports
from sauce.lib.auth import has_teacher
from sauce.model import Lesson, Team, Student, Sheet, Assignment, Test, Event, Teacher, NewsItem, DBSession
from sauce.controllers.crc import *
from tgext.crud.controller import CrudRestControllerHelpers, CrudRestController, EasyCrudRestController

log = logging.getLogger(__name__)

class EventAdminController(TGController):
    ''''''
    
    def __init__(self, event, **kw):
        
        self.event = event
        
        model_items = [Event, Lesson, Student, Team, Sheet, Assignment, Test, Teacher, NewsItem]
        self.menu_items = dict([(m.__name__.lower(), m) for m in model_items])
        
        self.events = EventsCrudController(inject=dict(teacher=request.teacher),
                                           filter_bys=dict(id=self.event.id),
                                           menu_items=self.menu_items, **kw)
        
        self.lessons = LessonsCrudController(inject=dict(event=self.event),
                                             filter_bys=dict(event_id=self.event.id),
                                             menu_items=self.menu_items, **kw)
        
        self.teams = TeamsCrudController(#filters=[Team.lesson_id.in_((l.id for l in self.event.lessons))],
                                         menu_items=self.menu_items, **kw)
        
        self.students = StudentsCrudController(#filters=[Student.id.in_((s.id for l in self.event.lessons for t in l.teams for s in t.students))],
                                               menu_items=self.menu_items, **kw)
        
        self.teachers = TeachersCrudController(#filters=[Teacher.id.in_((l.teacher.id for l in self.event.lessons))],
                                               menu_items=self.menu_items, **kw)
        
        
        self.sheets = SheetsCrudController(inject=dict(event=self.event, teacher=request.teacher),
                                           filter_bys=dict(event_id=self.event.id),
                                           menu_items=self.menu_items, **kw)
        
        self.assignments = AssignmentsCrudController(inject=dict(teacher=request.teacher),
                                                     query_modifier=lambda qry: qry.join(Assignment.sheet).filter_by(event_id=self.event.id),
                                                     menu_items=self.menu_items, **kw)
        
        self.tests = TestsCrudController(inject=dict(teacher=request.teacher),
                                         query_modifier=lambda qry: qry.join(Test.assignment).join(Assignment.sheet).filter_by(event_id=self.event.id),
                                         menu_items=self.menu_items, **kw)
        
        self.newsitems = NewsItemController(inject=dict(teacher=request.teacher),
                                            menu_items=self.menu_items, **kw)
        
        self.allow_only = Any(has_teacher(self.event),
                              has_permission('manage'),
                              msg=u'You have no permission to manage this Event'
                              )
        
    
    @without_trailing_slash
    @expose('sauce.templates.event_admin')
    def index(self):
        c.crud_helpers = CrudRestControllerHelpers()
        c.menu_items = self.menu_items
        return dict(page='events', event=self.event, menu_items=self.menu_items)
