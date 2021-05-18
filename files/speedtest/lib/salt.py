import json

import salt.client

def run(asset_id, cmd):
    """Run a command on salt minion."""
    local = salt.client.LocalClient('/etc/128technology/salt/master')
    result = local.cmd(asset_id, 'cmd.run', [cmd])[asset_id]
    if 'command not found' in result:
        warn('Error on node:', asset_id, result)
    return result

def retrieve_result(asset_id, results_file):
    results = {}
    cmd = 'cat {}'.format(results_file)
    try:
        result = run(asset_id, cmd)
        results_dict = json.loads(result)
        return results_dict
    except json.JSONDecodeError:
        return None
