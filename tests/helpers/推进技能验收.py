"""只对测试新局提交正常合法行动；不注入、改写或替换主持快照。"""
import json
import sys
from uuid import uuid4

from langrensha.full_game import pending
from langrensha.service import GameService

path, game_id, target_tool = sys.argv[1:]
assert target_tool in {'antidote', 'poison', 'shoot', 'reveal', 'signup'}
service = GameService(path)
steps = []
for _ in range(250):
    state = service.host_snapshot(game_id)
    human = service.bind_player(game_id, 1).view()
    expected_role = {'antidote': 'witch', 'poison': 'witch', 'shoot': 'hunter',
                     'reveal': 'idiot', 'signup': 'hunter'}[target_tool]
    assert human['role'] == expected_role
    if target_tool in human['tools']:
        print(json.dumps({'game_id': game_id, 'phase': state['phase'],
                          'role': human['role'], 'alive': human['players'][0]['alive'],
                          'tool': target_tool, 'legal_actions': steps}, ensure_ascii=False))
        break
    actors = pending(state)
    assert actors, 'game ended before requested legal skill window'
    actor = actors[0]
    session = service.bind_player(game_id, actor)
    view = session.view()
    tool, payload = 'abstain', {}
    if 'wolf_vote' in view['tools']:
        if target_tool in {'shoot', 'signup'}:
            tool, payload = 'wolf_vote', {'target': 1}
        elif target_tool in {'antidote', 'poison'}:
            target = next(p['seat'] for p in state['players']
                          if p['alive'] and p['role'] == 'villager' and p['seat'] != 1)
            tool, payload = 'wolf_vote', {'target': target}
    elif 'exile_vote' in view['tools'] and target_tool == 'reveal' and actor != 1:
        tool, payload = 'exile_vote', {'target': 1}
    assert tool in view['tools'], (view['phase'], actor, tool, view['tools'])
    session.submit({'request_id': str(uuid4()), 'phase_id': view['phase_id'],
                    'expected_version': view['version'], 'tool': tool, 'payload': payload})
    steps.append({'actor': actor, 'phase': view['phase'], 'tool': tool, **payload})
else:
    raise RuntimeError('requested skill window not reached by 250 legal actions')
