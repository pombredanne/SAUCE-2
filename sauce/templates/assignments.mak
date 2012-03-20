<%inherit file="local:templates.master"/>

<%def name="title()">
  Assignments
</%def>

<h2>Assignments</h2>

% if assignments:
  <h3>Current Assignments</h3>
  <dl>
      % for assignment in assignments.items:
        <dt>${h.link(assignment.name, tg.url('/assignments/%d' % assignment.id))}</dt>
        <dd>${assignment.description | n, h.striphtml }</dd>
      % endfor
  </dl>
  <p>${assignments.pager('Pages: $link_previous ~2~ $link_next')}</p>
 % endif
% if past_assignments:
  <h3>Past Assignments</h3>
  <dl>
      % for assignment in past_assignments.items:
        <dt>${h.link(assignment.name, tg.url('/assignments/%d' % assignment.id))}</dt>
        <dd>${assignment.description | n, h.striphtml }</dd>
      % endfor
  </dl>
  <p>${assignments.pager('Pages: $link_previous ~2~ $link_next')}</p>
 % endif

