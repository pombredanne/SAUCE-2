#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Perform various fixes due to bugs in admin interface.

@author: moschlar
"""
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

import os
import sys
from argparse import ArgumentParser
import traceback

from sqlalchemy.exc import IntegrityError

from paste.deploy import appconfig
from sauce.config.environment import load_environment
from sauce import model
from sauce.model import DBSession as Session

import transaction


def load_config(filename):
    conf = appconfig('config:' + os.path.abspath(filename))
    load_environment(conf.global_conf, conf.local_conf)


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("conf_file", help="configuration to use")
    return parser.parse_args()


def main():
    args = parse_args()
    load_config(args.conf_file)

    #print model.DBSession.query(model.User.user_name).all()

    events = Session.query(model.Event).all()

    print [(i, e.name) for i, e in enumerate(events)]

    event_id = raw_input('event_id: ')
    event = events[int(event_id)]

    fix_languages = raw_input("Allow all languages on all assignments? [y]")

    if fix_languages == 'y':
        l = Session.query(model.Language).all()

        for a in Session.query(model.Assignment).filter_by(event_id=event.id).all():
            a = Session.merge(a)
            a.allowed_languages = l
            Session.add(a)

        try:
            transaction.commit()
        except IntegrityError:
            print traceback.format_exc()
            transaction.abort()

    fix_visible_tests = raw_input("Fix boolean visible attribute on tests? [y]")

    if fix_visible_tests == 'y':
        for a in Session.query(model.Assignment).filter_by(event_id=event.id).all():
            a = Session.merge(a)
            print u'Assignment: %s' % a.name
            for t in a.tests:
                print u'Test %d, Output length %d' % (t.id, len(t.output))
                visible = raw_input('Make test visible? [y]')
                if visible == 'y':
                    t.visible = True
                    Session.add(t)
            try:
                transaction.commit()
            except IntegrityError:
                print traceback.format_exc()
                transaction.abort()


if __name__ == '__main__':
    print >>sys.stderr, 'Do not use this program unmodified.'
    sys.exit(1)
    sys.exit(main())
