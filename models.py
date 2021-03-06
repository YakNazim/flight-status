import config
import os
import redis

REDIS_URL = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')
r = redis.StrictRedis.from_url(REDIS_URL)

TAXONOMY = {
    "types": {
        "launch":   {"contains": ["system"]},
        "system":   {"contains": ["module"]},
        "module":   {"contains": ["part", "software"]},
        "part":     {"contains": []},
        "software": {"contains": []},
    },
    "top": "launch",
}

def gen_key(name):
    return name.replace(' ', '-').lower()


def get_fields(typ):
    fields = [
        {
            'key':  "name",
            'name': "Name",
            'type': "text",
        },
        {
            'key':  "desc",
            'name': "Description",
            'type': "textarea",
        },
    ]
    if typ == TAXONOMY['top']:
        fields.append({
            'key': "date",
            'name': "Date/Time",
            'type': "date",
        })

    if len(TAXONOMY['types'][typ]['contains']) == 0:
        fields.append({
            'key': "status",
            'name': "Status",
            'type': "status",
        })

    return fields


def add_new(typ, form):
    #TODO: sanitize
    name = form['name']
    desc = form['desc']
    key  = gen_key(name)
    key  = config.ORG.lower()+'-'+typ+'-'+key

    set_key = config.ORG.lower()+'-'+typ+'-list'

    r.hset(key, 'name', name)
    r.hset(key, 'desc', desc)
    r.sadd(set_key, key)

def delete(typ, key):
    set_key = config.ORG.lower()+'-'+typ+'-list'

    r.srem(set_key, key)
    r.delete(key)

def update(typ, form):
    key = form['key']
    set_key = config.ORG.lower()+'-'+typ+'-list'
    for field in get_fields(typ):
        r.hset(key, field['key'], form[field['key']])
    r.sadd(set_key, key)

def add_member(typ, member_typ, form):
    parent_key = form['key']
    child_type = member_typ
    child_key = form[parent_key+member_typ+'key']

    member_child_list_key = parent_key+'-'+child_type+'-children'
    r.sadd(member_child_list_key, child_key)
    print parent_key, child_key, member_child_list_key

def get_children(typ, key):    
    member_list_key = key+'-'+typ+'-children'
    member_collection = []
    for member_key in r.smembers(member_list_key):
        m_entry = {}
        m_entry['key']  = member_key
        for field in get_fields(typ):
            m_entry[field['key']] = r.hget(member_key, field['key'])
            if field['key'] == "status":
                try:
                    m_entry['status'] = int(m_entry['status'])
                except:
                    m_entry['status'] = 0
        member_collection.append(m_entry)

    return member_collection 

# Return collection of instances of type typ
def get_all_of_type(typ):
    # The key for the list of this type
    set_key = config.ORG.lower()+'-'+typ+'-list'

    keys    = r.smembers(set_key)   #list of keys in collection
    fields  = get_fields(typ)       #list of fields for this type

    collection = []
    for key in keys:
        entry = {}

        # main fields:
        entry['key']  = key
        for field in get_fields(typ):
            entry[field['key']] = r.hget(key, field['key'])

        if len(TAXONOMY['types'][typ]['contains']) > 0:
            entry['allow-members'] = True
        else:
            entry['allow-members'] = False

         # get members:
        members = []
        num_members = 0
        for member_type in TAXONOMY['types'][typ]['contains']:
            member = {}
            member['key'] = member_type
            member['name'] = member_type.replace('_',' ').title()

            # Get the name, descriptions, and keys for typeahead
            all_members = []
            for k in r.smembers(config.ORG.lower()+'-'+member_type+'-list'):
                n = r.hget(k, 'name')
                d = r.hget(k, 'desc')
                all_members.append(n+' ('+d+')|'+k)

            member['all'] = all_members

            member['members'] = get_children(member_type, key)
            num_members += len(member['members'])
            members.append(member)

        entry['members'] = members
        entry['n_members'] = num_members
        collection.append(entry)
    return collection
