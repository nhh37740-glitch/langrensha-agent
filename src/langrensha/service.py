"""受信主持入口及受限玩家会话。此层为进程内接口，不提供网络身份认证。"""

from datetime import UTC, datetime

from .rules import Rejected as Rejected
from .rules import create_game, player_view, reduce_action, seat_number
from .store import Store


def utc_now():
    return datetime.now(UTC).isoformat()


class GameService:
    """仅供受信应用层持有；不可把本对象或数据库交给玩家/模型。"""

    def __init__(self, database):
        self.store = Store(database)

    def create(self, *, human_seat=1, human_role=None, rng=None):
        state = create_game(human_seat=human_seat, human_role=human_role, now=utc_now(), rng=rng)
        with self.store.transaction() as db:
            self.store.save(db, state, create=True)
        return state["id"]

    def bind_player(self, game_id, seat):
        """主持在已认证身份后绑定；未来 HTTP/AI 工具参数不得暴露此方法。"""
        seat_number(seat)
        with self.store.transaction() as db:
            self.store.load(db, game_id)
        return PlayerSession(self, game_id, seat)

    def host_snapshot(self, game_id):
        with self.store.transaction() as db:
            return self.store.load(db, game_id)

    def host_rejections(self, game_id):
        with self.store.transaction() as db:
            rows = db.execute(
                "SELECT actor,code,time FROM rejections WHERE game_id=? ORDER BY id", (game_id,)
            ).fetchall()
        return [{"actor": actor, "code": code, "time": time} for actor, code, time in rows]

    def _view(self, game_id, actor):
        with self.store.transaction() as db:
            return player_view(self.store.load(db, game_id), actor)

    def _submit(self, game_id, actor, command):
        error = None
        with self.store.transaction() as db:
            state = self.store.load(db, game_id)
            try:
                updated, result = reduce_action(state, actor, command, now=utc_now())
            except Rejected as exc:
                error = exc
                db.execute(
                    "INSERT INTO rejections(game_id,actor,code,time) VALUES (?,?,?,?)",
                    (game_id, actor, exc.code, utc_now()),
                )
            else:
                self.store.save(db, updated)
        # 拒绝审计先提交，再抛异常；不修改对局快照或递增版本。
        if error is not None:
            raise error
        return result


class PlayerSession:
    """操作者由受信层绑定；submit 只接受窗口、版本、工具和参数。"""

    def __init__(self, service, game_id, actor):
        self._service, self._game_id, self._actor = service, game_id, actor

    def view(self):
        return self._service._view(self._game_id, self._actor)

    def submit(self, command):
        return self._service._submit(self._game_id, self._actor, command)
