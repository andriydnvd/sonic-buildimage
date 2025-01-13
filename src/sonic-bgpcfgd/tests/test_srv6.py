from unittest.mock import MagicMock, patch

from bgpcfgd.directory import Directory
from bgpcfgd.template import TemplateFabric
from bgpcfgd.managers_srv6 import SRv6Mgr

def constructor():
    cfg_mgr = MagicMock()

    common_objs = {
        'directory': Directory(),
        'cfg_mgr':   cfg_mgr,
        'tf':        TemplateFabric(),
        'constants': {},
    }

    loc_mgr = SRv6Mgr(common_objs, "CONFIG_DB", "SRV6_MY_LOCATORS")
    sid_mgr = SRv6Mgr(common_objs, "CONFIG_DB", "SRV6_MY_SIDS")

    return loc_mgr, sid_mgr

def op_test(mgr: SRv6Mgr, op, args, expected_ret, expected_cmds):
    op_test.push_list_called = False
    def push_list_checker(cmds):
        op_test.push_list_called = True
        assert len(cmds) == len(expected_cmds)
        for i in range(len(expected_cmds)):
            assert cmds[i].lower() == expected_cmds[i].lower()
        return True
    mgr.cfg_mgr.push_list = push_list_checker

    if op == 'SET':
        ret = mgr.set_handler(*args)
        mgr.cfg_mgr.push_list = MagicMock()
        assert expected_ret == ret
    elif op == 'DEL':
        mgr.del_handler(*args)
        mgr.cfg_mgr.push_list = MagicMock()
    else:
        mgr.cfg_mgr.push_list = MagicMock()
        assert False, "Unexpected operation {}".format(op)

    if expected_ret and expected_cmds:
        assert op_test.push_list_called, "cfg_mgr.push_list wasn't called"
    else:
        assert not op_test.push_list_called, "cfg_mgr.push_list was called"

def test_locator_add():
    loc_mgr, _ = constructor()

    op_test(loc_mgr, 'SET', ("loc1", {
        'prefix': 'fcbb:bbbb:1::'
    }), expected_ret=True, expected_cmds=[
        'segment-routing',
        'srv6',
        'locators',
        'locator loc1',
        'prefix fcbb:bbbb:1::/48 block-len 32 node-len 16 func-bits 16',
        'behavior usid'
    ])

    assert loc_mgr.directory.path_exist(loc_mgr.db_name, loc_mgr.table_name, "loc1")

def test_locator_del():
    loc_mgr, _ = constructor()
    loc_mgr.set_handler("loc1", {'prefix': 'fcbb:bbbb:1::'})

    op_test(loc_mgr, 'DEL', ("loc1",), expected_ret=True, expected_cmds=[
        'segment-routing',
        'srv6',
        'locators',
        'no locator loc1'
    ])

    assert not loc_mgr.directory.path_exist(loc_mgr.db_name, loc_mgr.table_name, "loc1")

def test_uN_add():
    loc_mgr, sid_mgr = constructor()
    assert loc_mgr.set_handler("loc1", {'prefix': 'fcbb:bbbb:1::'})

    op_test(sid_mgr, 'SET', ("loc1|FCBB:BBBB:1:F1::", {
        'action': 'uN'
    }), expected_ret=True, expected_cmds=[
        'segment-routing',
        'srv6',
        'static-sids',
        'sid fcbb:bbbb:1:f1::/64 locator loc1 behavior uN'
    ])

    assert sid_mgr.directory.path_exist(sid_mgr.db_name, sid_mgr.table_name, "loc1|fcbb:bbbb:1:f1::")

def test_uDT46_add_vrf1():
    loc_mgr, sid_mgr = constructor()
    assert loc_mgr.set_handler("loc1", {'prefix': 'fcbb:bbbb:1::'})

    op_test(sid_mgr, 'SET', ("loc1|FCBB:BBBB:1:F2::", {
        'action': 'uDT46',
        'decap_vrf': 'Vrf1'
    }), expected_ret=True, expected_cmds=[
        'segment-routing',
        'srv6',
        'static-sids',
        'sid fcbb:bbbb:1:f2::/64 locator loc1 behavior uDT46 vrf Vrf1'
    ])

    assert sid_mgr.directory.path_exist(sid_mgr.db_name, sid_mgr.table_name, "loc1|fcbb:bbbb:1:f2::")

def test_uN_del():
    loc_mgr, sid_mgr = constructor()
    assert loc_mgr.set_handler("loc1", {'prefix': 'fcbb:bbbb:1::'})
    
    # add uN function first
    assert sid_mgr.set_handler("loc1|FCBB:BBBB:1:F1::", {
        'action': 'uN'
    })

    # test the deletion
    op_test(sid_mgr, 'DEL', ("loc1|FCBB:BBBB:1:F1::",),
            expected_ret=True, expected_cmds=[
            'segment-routing',
            'srv6',
            'static-sids',
            'no sid fcbb:bbbb:1:f1::/64 locator loc1 behavior uN'
    ])

    assert not sid_mgr.directory.path_exist(sid_mgr.db_name, sid_mgr.table_name, "loc1|fcbb:bbbb:1:f1::")

def test_uDT46_del_vrf1():
    loc_mgr, sid_mgr = constructor()
    assert loc_mgr.set_handler("loc1", {'prefix': 'fcbb:bbbb:1::'})
    
    # add a uN action first to make the uDT46 action not the last function
    assert sid_mgr.set_handler("loc1|FCBB:BBBB:1:F1::", {
        'action': 'uN'
    })

    # add the uDT46 action
    assert sid_mgr.set_handler("loc1|FCBB:BBBB:1:F2::", {
        'action': 'uDT46',
        "decap_vrf": "Vrf1"
    })

    # test the deletion of uDT46
    op_test(sid_mgr, 'DEL', ("loc1|FCBB:BBBB:1:F2::",),
            expected_ret=True, expected_cmds=[
            'segment-routing',
            'srv6',
            'static-sids',
            'no sid fcbb:bbbb:1:f2::/64 locator loc1 behavior uDT46 vrf Vrf1'
    ])

    assert sid_mgr.directory.path_exist(sid_mgr.db_name, sid_mgr.table_name, "loc1|fcbb:bbbb:1:f1::")
    assert not sid_mgr.directory.path_exist(sid_mgr.db_name, sid_mgr.table_name, "loc1|fcbb:bbbb:1:f2::")

def test_invalid_add():
    _, sid_mgr = constructor()

    # test the addition of a SID with a non-existent locator
    op_test(sid_mgr, 'SET', ("loc2|FCBB:BBBB:21:F1::", {
        'action': 'uN'
    }), expected_ret=False, expected_cmds=[])

    assert not sid_mgr.directory.path_exist(sid_mgr.db_name, sid_mgr.table_name, "loc2|fcbb:bbbb:21:f1::")