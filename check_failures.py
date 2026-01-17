import json
r=json.load(open('comprehensive_validation_results.json'))
f=[x for x in r['results'] if not x['gates_passed']]
print(f'{len(f)} failures:\n')
for i,x in enumerate(f):
    print(f'{i+1}. {x["query"][:60]:60} -> {x.get("response_type_pred","?"):15}')
