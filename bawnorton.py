# Code from Andrew6rant's README.md
# https://github.com/Andrew6rant/Andrew6rant

import hashlib
import os
from xml.dom import minidom

import requests

HEADERS = {'authorization': 'token ' + os.getenv('README_TOKEN')}
USERNAME = os.getenv('USERNAME')

def recursive_loc(owner, repo_name, data, addition_total=0, deletion_total=0, my_commits=0, cursor=None):
    query = '''
    query ($repo_name: String!, $owner: String!, $cursor: String) {
        repository(name: $repo_name, owner: $owner) {
            defaultBranchRef {
                target {
                    ... on Commit {
                        history(first: 100, after: $cursor) {
                            totalCount
                            edges {
                                node {
                                    ... on Commit {
                                        committedDate
                                    }
                                    author {
                                        user {
                                            id
                                        }
                                    }
                                    deletions
                                    additions
                                }
                            }
                            pageInfo {
                                endCursor
                                hasNextPage
                            }
                        }
                    }
                }
            }
        }
    }'''
    variables = {'repo_name': repo_name, 'owner': owner, 'cursor': cursor}
    request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': variables},
                            headers=HEADERS)
    if request.status_code == 200:
        if request.json()['data']['repository']['defaultBranchRef'] is not None:
            return loc_counter_one_repo(owner, repo_name, data,
                                        request.json()['data']['repository']['defaultBranchRef']['target']['history'],
                                        addition_total, deletion_total, my_commits)
        else:
            return 0
    if request.status_code == 403:
        raise Exception(
            'Too many requests in a short amount of time!\nYou\'ve hit the non-documented anti-abuse limit!')
    raise Exception('recursive_loc() has failed with a', request.status_code, request.text)


def loc_counter_one_repo(owner, repo_name, data, history, addition_total, deletion_total, my_commits):
    for node in history['edges']:
        if node['node']['author']['user'] == OWNER_ID:
            my_commits += 1
            addition_total += node['node']['additions']
            deletion_total += node['node']['deletions']

    if history['edges'] == [] or not history['pageInfo']['hasNextPage']:
        return addition_total, deletion_total, my_commits
    else:
        return recursive_loc(owner, repo_name, data, addition_total, deletion_total, my_commits,
                             history['pageInfo']['endCursor'])


def loc_query(owner_affiliation, force_cache=False, cursor=None, edges=None):
    if edges is None:
        edges = []
    query = '''
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 50, after: $cursor, ownerAffiliations: $owner_affiliation) {
            edges {
                node {
                    ... on Repository {
                        nameWithOwner
                        defaultBranchRef {
                            target {
                                ... on Commit {
                                    history {
                                        totalCount
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }'''
    variables = {'owner_affiliation': owner_affiliation, 'login': USERNAME, 'cursor': cursor}
    request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': variables},
                            headers=HEADERS)
    if request.status_code == 200:
        if request.json()['data']['user']['repositories']['pageInfo']['hasNextPage']:
            edges += request.json()['data']['user']['repositories']['edges']
            return loc_query(owner_affiliation, force_cache,
                             request.json()['data']['user']['repositories']['pageInfo']['endCursor'], edges)
        else:
            return cache_builder(edges + request.json()['data']['user']['repositories']['edges'], force_cache)
    raise Exception('loc_query() has failed with a', request.status_code, request.text)


def cache_builder(edges, force_cache, loc_add=0, loc_del=0):
    cached = True
    filename = f"cache/{hashlib.sha256(USERNAME.encode('utf-8')).hexdigest()}.txt"
    try:
        with open(filename, 'r') as f:
            data = f.readlines()
    except FileNotFoundError:
        data = []
        with open(filename, 'w') as f:
            f.writelines(data)

    if len(data) != len(edges) or force_cache:
        cached = False
        flush_cache(edges, filename)
        with open(filename, 'r') as f:
            data = f.readlines()

    for edge_index in range(len(edges)):
        repo_hash, commit_count, *__ = data[edge_index].split()
        if repo_hash == hashlib.sha256(edges[edge_index]['node']['nameWithOwner'].encode('utf-8')).hexdigest():
            try:
                if int(commit_count) != edges[edge_index]['node']['defaultBranchRef']['target']['history']['totalCount']:
                    owner, repo_name = edges[edge_index]['node']['nameWithOwner'].split('/')
                    loc = recursive_loc(owner, repo_name, data)
                    data[edge_index] = repo_hash + ' ' + str(
                        edges[edge_index]['node']['defaultBranchRef']['target']['history'][
                            'totalCount']) + f' {loc[2]} {loc[0]} {loc[1]}\n'
            except TypeError:
                data[edge_index] = repo_hash + ' 0 0 0 0\n'
    with open(filename, 'w') as f:
        f.writelines(data)
    for line in data:
        loc = line.split()
        loc_add += int(loc[3])
        loc_del += int(loc[4])
    return [loc_add, loc_del, loc_add - loc_del, cached]


def flush_cache(edges, filename):
    with open(filename, 'r') as f:
        data = f.readlines()
    with open(filename, 'w') as f:
        f.writelines(data)
        for node in edges:
            f.write(hashlib.sha256(node['node']['nameWithOwner'].encode('utf-8')).hexdigest() + ' 0 0 0 0\n')


def svg_overwrite(filename):
    svg = minidom.parse(filename)
    f = open(filename, mode='w', encoding='utf-8')
    tspan = svg.getElementsByTagName('tspan')
    text_width = len(f"{loc_data['total_loc']} ({loc_data['total_loc_add']}, {loc_data['total_loc_del']})")
    svg.getElementsByTagName('text')[0].setAttribute('x', str((400 - (text_width * 9.5)) / 2))
    tspan[2].firstChild.data = loc_data["total_loc"]
    tspan[3].firstChild.data = loc_data["total_loc_add"]
    tspan[4].firstChild.data = loc_data["total_loc_del"]
    f.write(svg.toxml('utf-8').decode('utf-8'))
    f.close()


def user_getter(username):
    query = '''
    query($login: String!){
        user(login: $login) {
            id
            createdAt
        }
    }'''
    variables = {'login': username}
    request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': variables},
                            headers=HEADERS)
    if request.status_code == 200:
        return {'id': request.json()['data']['user']['id']}, request.json()['data']['user']['createdAt']
    raise Exception('user_getter() has failed with a', request.status_code, request.text)


if __name__ == '__main__':
    OWNER_ID = user_getter(USERNAME)[0]
    total_loc = loc_query(['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'])
    loc_data = {
        'total_loc': f"{total_loc[2]:,}",
        'total_loc_add': f"{total_loc[0]:,}++",
        'total_loc_del': f"{total_loc[1]:,}--",
    }

    svg_overwrite('dark_mode.svg')
    svg_overwrite('light_mode.svg')
