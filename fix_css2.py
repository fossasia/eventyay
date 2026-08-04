with open('app/eventyay/static/pretixcontrol/css/advanced-filter.css', 'r') as f:
    content = f.read()

# 1. Update .advanced-filter-search
content = content.replace(
'''.advanced-filter-search {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 12px;
  width: 100%;
  margin-bottom: 15px;
}''',
'''.advanced-filter-search {
  display: block;
  width: 100%;
  margin-bottom: 15px;
}
/* Ensure the container clears its floating children */
.advanced-filter-search::after {
  content: "";
  clear: both;
  display: table;
}'''
)

# 2. Update .advanced-filter-go-form
content = content.replace(
'''.advanced-filter-go-form {
  flex: 0 0 auto;
}''',
'''.advanced-filter-go-form {
  float: left;
  margin-right: 12px;
  margin-bottom: 12px;
}'''
)

# 3. Update .advanced-filter-search-form
content = content.replace(
'''.advanced-filter-search-form {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  flex: 1 1 0;
  min-width: 0;
}''',
'''.advanced-filter-search-form {
  display: block;
}'''
)

# 4. Update .advanced-filter-advanced
content = content.replace(
'''.advanced-filter-advanced {
  flex: 0 0 100%;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 12px;
  background: #fafafa;
}''',
'''.advanced-filter-advanced {
  clear: both;
  width: 100%;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 12px;
  background: #fafafa;
  margin-top: 12px;
}'''
)

# Wait, in media query for max-width: 767px, maybe we want go-form to take full width?
# Currently there is no rule for .advanced-filter-go-form in media query.
content = content.replace(
'''  .advanced-filter-search {
    flex-direction: column;
  }''',
'''  .advanced-filter-go-form {
    float: none;
    width: 100%;
    margin-right: 0;
  }
  .advanced-filter-search {
    display: block;
  }'''
)


with open('app/eventyay/static/pretixcontrol/css/advanced-filter.css', 'w') as f:
    f.write(content)
