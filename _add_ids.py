with open('dashboard/templates/v3/pages/trade_operations.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add IDs to panel divs
old1 = '<div class="lg:col-span-8 bg-surface-container border border-outline-variant rounded-lg flex flex-col"'
new1 = '<div id="to-executions-table" class="lg:col-span-8 bg-surface-container border border-outline-variant rounded-lg flex flex-col"'

old2 = '<div class="lg:col-span-4 bg-surface-container border border-outline-variant rounded-lg flex flex-col"'
new2 = '<div id="to-exec-quality" class="lg:col-span-4 bg-surface-container border border-outline-variant rounded-lg flex flex-col"'

old3 = '<div class="lg:col-span-7 bg-surface-container border border-outline-variant rounded-lg flex flex-col"'
new3 = '<div id="to-history-log" class="lg:col-span-7 bg-surface-container border border-outline-variant rounded-lg flex flex-col"'

content = content.replace(old1, new1)
content = content.replace(old2, new2)
content = content.replace(old3, new3)

with open('dashboard/templates/v3/pages/trade_operations.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('IDs added successfully')
