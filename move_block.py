import re

with open('app/eventyay/orga/templates/orga/review/dashboard.html', 'r') as f:
    content = f.read()

# find the review-toolbar block
start_str = '    <div class="review-toolbar mb-2 d-flex">'
end_str = '    </div>\n\n    {% include "orga/includes/review_filter_form.html" %}'

start_idx = content.find(start_str)
end_idx = content.find(end_str)

toolbar_content = content[start_idx:end_idx + 10]

new_dashboard_content = content[:start_idx] + '    {% include "orga/includes/review_filter_form.html" %}' + content[end_idx + len(end_str):]

with open('app/eventyay/orga/templates/orga/review/dashboard.html', 'w') as f:
    f.write(new_dashboard_content)

with open('app/eventyay/orga/templates/orga/includes/review_filter_form.html', 'a') as f:
    f.write("\n{% block before_form %}\n")
    f.write(toolbar_content)
    f.write("\n{% endblock before_form %}\n")

print("Done")
