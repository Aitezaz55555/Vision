import re

tests = [
    'search for quantum computing',
    'search google for quantum computing',
    'search on google for quantum computing',
    'search for quantum computing on google',
    'search for python tutorials on youtube',
    'search youtube for python tutorials',
    'search on youtube'
]

for t in tests:
    cmd = t.strip()
    plat = None
    query = cmd
    # Check for explicit platform
    m_plat = re.search(r'\b(?:on|in)?\s*(youtube|google)\b', cmd, re.I)
    if m_plat:
        plat = m_plat.group(1).lower()
        query = re.sub(r'\b(?:on|in)?\s*(youtube|google)\b', '', query, flags=re.I).strip()

    # remove search prefixes
    query = re.sub(r'^(?:now )?(?:search (?:for )?|find |look up )', '', query, flags=re.I).strip()
    query = re.sub(r'^(?:for |about |tutorials on |videos of )', '', query, flags=re.I).strip()
    print(f'{t:45} -> plat={plat}, query="{query}"')
