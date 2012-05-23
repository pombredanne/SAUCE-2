<%inherit file="local:templates.master"/>
<%namespace file="local:templates.sheets" name="sheets" />
<%namespace file="local:templates.lists" name="lists" />
<%namespace file="local:templates.misc" import="times_dl" />

<%def name="title()">
  ${event.name}
</%def>

<div class="page-header">
  <h1>${event.name} <small>Event</small></h1>
</div>

${self.details(event)}

<%def name="details(event)">

<p class="description">${event.description | n }</p>

% if event.teacher:
  <dl>
    <dt>Contact:</dt>
    <dd>${event.teacher.link}</dd>
  </dl>
% endif

% if event.type == 'contest':
  ${times_dl(event)}
% endif

  % if event.sheets:
    <h2><a href="${event.url}/sheets">Sheets</a></h2>
    
    % if event.current_sheets:
      <h3>Current sheets</h3>
      ${sheets.list(event.current_sheets)}
    % endif

    % if event.future_sheets:
      <h3>Future sheets</h3>
      ${sheets.list_short(event.future_sheets)}
    % endif

    % if event.previous_sheets:
      <h3>Previous sheets</h3>
      ${sheets.list_short(event.previous_sheets)}
    % endif
  % endif


% if event.news:
  <h2>News</h2>
  % if request.teacher:
    ${lists.news(event.news)}
  % else:
    ${lists.news((news for news in event.news if news.public))}
  % endif
% endif

</%def>
