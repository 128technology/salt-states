import logging

log = logging.getLogger(__name__)

def _changes(name,
             current_user,
             role=None,
             enabled=None,
             fullName=None,
             password=None):
    '''
    Return a dict of the changes required if the user is present,
    otherwise return False.
    '''
    change = {}
    if enabled is not None:
        try:
            if current_user['enabled'] != enabled:
                change['enabled'] = enabled
        except KeyError:
            change['enabled'] = enabled
    if role is not None:
        try:
            if current_user['role'] != role:
                change['role'] = role
        except KeyError:
            change['role'] = role
    if fullName is not None:
        try:
            if current_user['fullName'] != fullName:
                change['fullName'] = fullName
        except KeyError:
            change['fullName'] = fullName
    if password is not None:
        current_hash = __salt__['shadow.info'](name)['passwd']
        # If account is disabled, disregard the initial !
        if current_hash[0] == '!':
            current_hash = current_hash[1:]
        crypt_salt = current_hash.split('$')[2]
        new_hash = __salt__['shadow.gen_password'](password, crypt_salt=crypt_salt)
        if current_hash != new_hash:
            change['password'] = password

    return change

def present(name,
            role=None,
            enabled=True,
            fullName=None,
            password=None):
    '''
    Ensure that the named user is present with the specified properies

    name
        The name of the 128T user to manage

    role
        The role of the user, user or admin

    enabled : True
        If set to ``False``, the user account will be locked

    fullName
        The user's full name

    password
        The user's password
    '''

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0} is present and up to date'.format(name)}

    if role and type(role) is not list:
        role = [role]

    t128_users = __salt__['t128_users.get_users']()
    changes = False
    try:
        current_user = t128_users[name]
        changes = _changes(name,
                       current_user,
                       role=role,
                       enabled=enabled,
                       fullName=fullName,
                       password=password)
    except KeyError:
        pass

    if changes:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('The following user attributes are set to be '
                              'changed:\n{}'.format(changes))
            return ret
        # The user is present
        if __salt__['t128_users.modify_user'](name, 
                                              role=role, 
                                              enabled=enabled, 
                                              fullName=fullName,
                                              password=password):
            ret['changes'] = changes
            ret['comment'] = 'Updated user {0}'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'There was a problem updating user {0}'.format(name)

    if changes is False:
        # The user is not present, make it!
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User {0} set to be added'.format(name)
            return ret
        if __salt__['t128_users.add_user'](name, 
                                           role=role, 
                                           enabled=enabled, 
                                           fullName=fullName,
                                           password=password):
            ret['comment'] = 'New user {0} created'.format(name)
            ret['changes'] = __salt__['t128_users.get_users']()[name]
        else:
            ret['comment'] = 'Failed to create new user {0}'.format(name)
            ret['result'] = False

    return ret


def absent(name):
    '''
    Ensure that the named user is absent

    name
        The name of the user to remove
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    users = __salt__['t128_users.get_users']()
    user = None
    try:
        user = users[name]
    except KeyError:
        ret['comment'] = 'User {0} is not present'.format(name)

    if __opts__['test']:
        ret['result'] = None
        if user:
            ret['comment'] = 'User {0} set for removal'.format(name)
        return ret

    if user:
        if __salt__['t128_users.delete_user'](name):
            ret['changes'][name] = 'removed'
            ret['comment'] = 'Removed user {0}'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to remove user {0}'.format(name)

    return ret

def manage_user_list(name, users, do_not_delete=["admin"]):
    '''
    Manage a list of users ensuring that all users in the list and users
    not found in the list are deleted.

    users
        List of dicts of users that may contain the following properties:

        name
            The name of the 128T user to manage

        role
            The role of the user, user or admin

        enabled : True
            If set to ``False``, the user account will be locked

        fullName
            The user's full name

        password
            The user's password

    do_not_delete : ["admin"]
        A list of user that, if found on the system but not in the list
        of users, will not be removed.  Admin will always be re-added
        to this list if absent.
    '''
    if "admin" not in do_not_delete:
        do_not_delete.append("admin")

    t128_users = __salt__['t128_users.get_users']()

    ret = {'name': users,
           'changes': {},
           'result': True,
           'comment': ''}

    if users:
        for user in users:
            username = None
            try:
                username = user['name']
            except KeyError:
                continue
            if username in t128_users.keys():
                # The user is present
                current_user = t128_users.pop(username)
                user_role = user.get('role', None)
                if user_role and type(user_role) is not list:
                    user_role = [user_role]
                changes = _changes(username, 
                               current_user,
                               role=user_role,
                               enabled=user.get('enabled'),
                               fullName=user.get('fullName'),
                               password=user.get('password'))
                if changes:
                    if __opts__['test']:
                        ret['result'] = None
                        ret['comment'] += ('The following attributes are set to be '
                                          'changed for user {0}:\n{1}'.format(username,changes))
                    else:
                        log.debug("changes: {}".format(changes))
                        log.debug("user: {}".format(user))
                        if __salt__['t128_users.modify_user'](**user):
                            ret['changes'][username] = changes
                            ret['comment'] += 'Updated user {0}\n'.format(username)
                        else:
                            ret['result'] = False
                            ret['comment'] += 'There was a problem updating user {0}\n'.format(username)
            else:
                # The user is not present, make it!
                if __opts__['test']:
                    ret['result'] = None
                    ret['comment'] += 'User {0} set to be added\n'.format(username)
                if __salt__['t128_users.add_user'](**user):
                    ret['comment'] += 'New user {0} created\n'.format(username)
                    ret['changes'][username] = __salt__['t128_users.get_users']()[username]
                else:
                    ret['comment'] += 'Failed to create new user {0}\n'.format(username)
                    ret['result'] = False

    # Anything left in here should be considered for deletion
    for username in t128_users.keys():
        if username not in do_not_delete:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] += 'User {0} set for removal\n'.format(username)
            else:
                if __salt__['t128_users.delete_user'](username):
                    ret['changes'][username] = 'removed'
                    ret['comment'] += 'Removed user {0}\n'.format(username)
                else:
                    ret['result'] = False
                    ret['comment'] += 'Failed to remove user {0}\n'.format(username)

    return ret
