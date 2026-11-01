# `STRATA_COALESCE_MIN_REQS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更は表示されなかった。外部ライブラリの環境変数は対象外。

## 役割

サーバーの batch 実行で、待機中の複数リクエストの prompt を同じ layer-major prefill に載せる coalescing を始めるために必要な、短時間内のリクエスト数を指定します。値は「最低いくつのリクエストが到着したら共有読み込みを試すか」の閾値です。これは `serve/server.py` が読むサーバー側の Python 環境変数で、Strata engine の C++/GPU 処理を直接切り替える値ではありません（読み取り: `serve/server.py:351`、batch 経路: `serve/server.py:2327-2336`）。

## 値と判定

モジュール読み込み時に `max(2, int(os.environ.get("STRATA_COALESCE_MIN_REQS") or 3))` で評価します（`serve/server.py:351`）。

| 環境値 | 判定後の閾値 |
|---|---:|
| 未設定 | 3 |
| 空文字 | 3（`or 3` により既定値へ） |
| 整数として読める値 `N`（`N >= 2`） | `N` |
| `1`、`0`、負数 | 2（`max(2, ...)` で下限化） |
| 整数に変換できない文字列（例: `abc`、`2.5`、空白だけ） | `int()` の `ValueError`。この箇所に fallback や警告処理はない |

上限 clamp はありません。Python の `int()` が値全体を変換し、閾値は整数になります。したがって `1.5` のような小数表記は無効です。`"0"` は空文字ではないため `int("0")` の後で下限値 2 になり、空文字の既定値 3 とは異なります。

## 有効になる条件

- `StrataEngine.generate()` が `self.batch` のある batch 経路を選ぶこと（`serve/server.py:2327-2336`）。
- `COALESCE_PREFILL > 1` かつ embedding 入力でないこと。新規 control-line 待ち登録時に prompt を保持し、batch admission ごとに `_coalesce()` を呼びます（`serve/server.py:1916-1918,2077-2080`）。`STRATA_COALESCE_PREFILL` が未設定または 1 以下なら、この閾値は使われません。
- engine がサーバーの `BCO` co-read プロトコルを扱えること。サーバーは選ばれた follower prompt を `BCO` 行で送り、`BCOK` 応答を受け付けます（`serve/server.py:1594-1595,1855-1859`）。Strata engine 側の batch loop には `BCO` 入力処理があります（`src/program/generate.cpp:13530`）。

OS、CUDA/HIP/SYCL、GPU 世代、build macro、モデル状態による閾値の差は、この値の読み取り・判定コードにはありません。CLI 引数による上書きもなく、この名前を読む箇所は `serve/server.py:351` の一箇所です。`STRATA_COALESCE_PREFILL` が機能の容量を、`STRATA_COALESCE_WAIT_MS` と `STRATA_COALESCE_BURST_MS` が待ち時間・到着窓を別途制御します（`serve/server.py:344-352`）。

## 実行時の詳細

サーバーは `_take_control()` で新規要求の到着時刻を `arrivals` に登録し、待ち行列にも要求を加えます（`serve/server.py:1747-1756`）。batch admission の `_coalesce()` は、現在の burst 窓（`COALESCE_BURST_MS`）内の到着数と `1 + len(wait_lens)` の大きい方を `recent` とします（`serve/server.py:1823-1827`）。この数には現在の leader 要求も含まれます。

`recent` が閾値未満で `COALESCE_WAIT_MS > 0` なら 10 ms 待って数え直します。それでも閾値未満なら coalescing をせず戻ります。閾値以上なら、`COALESCE_WAIT_MS > 0` の場合はさらに同値の時間だけ待ち、待機中要求から follower を選びます（`serve/server.py:1828-1837`）。したがって、閾値を満たすことは共有読み込みの試行条件であり、実際に follower が選ばれる保証ではありません。

follower 候補には prompt と request が保持されている必要があり、同じ request の再選択を避け、すでに予約済みの request を除外します。さらに prompt が 32 token 未満、leader と合わせた総 token 数が `COALESCE_TOKENS` を超える場合も除外し、空き slot がなければ選択を止めます。選択数は最大 `COALESCE_PREFILL - 1` 件です（`serve/server.py:1835-1854`）。選ばれた要求がある場合、サーバーは各 prompt を `BCO` 行として送信し、`[strata] coalesce: ...` を stdout に出します。候補が選ばれなければこのログは出ません（`serve/server.py:1855-1859`）。

値は Python モジュールのトップレベルで一度だけ読み取られ、グローバル定数 `COALESCE_MIN_REQS` に保存されます。稼働中に環境を変更しても反映されず、サーバープロセスの再起動が必要です（`serve/server.py:351`）。不正な整数文字列ではモジュール初期化中に `ValueError` が発生し、独自の fallback・警告・終了処理はこの代入箇所にはありません。

## 根拠

- 環境値の読み取り、空値 fallback、整数変換、下限 clamp: `serve/server.py:351`。
- 関連 coalescing 設定の既定値: `serve/server.py:344-352`。
- batch 経路と coalescing の呼び出し条件: `serve/server.py:1916-1918,2077-2080,2327-2336`。
- 到着数の算出、閾値判定、追加待機、follower の条件・選択上限、ログ: `serve/server.py:1821-1859`。
- `BCOK` の受信と engine 側の `BCO` 処理: `serve/server.py:1594-1595`; `src/program/generate.cpp:13530`。
- `docs/DETAILS.md` にはこの変数名の記載が見つからなかったため、性能値や速度向上は記載していません。
