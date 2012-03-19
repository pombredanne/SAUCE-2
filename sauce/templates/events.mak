<%inherit file="local:templates.master"/>

<%def name="title()">
  Events
</%def>

<h2>Events</h2>
  <p>Current Events: 
  <table>
      %for event in events.items:
      <tr>
          <th>${h.html.tags.link_to(event.name, tg.url('/events/%d' % event.id))}</th>
          <td>${event.description}</td>
      </tr>
      %endfor
  </table>
  ${events.pager('Pages: $link_previous ~2~ $link_next')}
  </p>

