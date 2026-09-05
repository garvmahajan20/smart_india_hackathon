import requests, re
text = requests.get('https://www.indiapost.gov.in/tenders', verify=False).text
links = re.findall(r'href=[\"\']([^\"\']+\.pdf)[\"\']', text, re.I)
print(len(links))
for l in links[:5]: print(l)

